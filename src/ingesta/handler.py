"""Lambda de ingesta: Banxico SIE -> Amazon S3 bronze.

Responsabilidad única: traer la respuesta ORIGINAL del SIE y guardarla tal cual
en el bucket bronze (versionado), con metadatos de ejecución. No transforma ni calcula nada;
eso le corresponde a la Lambda de validación y cálculo.

Modos de ejecución (campo "mode" del evento):
  * "daily" (por defecto): consulta el dato oportuno de cada serie.
  * "backfill": consulta un rango de fechas -> {"mode": "backfill",
    "start": "2026-01-01", "end": "2026-10-31", "series": ["SF43718"]}

Solo usa la biblioteca estándar de Python + boto3 (incluido en el runtime de Lambda).
"""

import gzip
import hashlib
import json
import logging
import os
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone

import boto3

LOG = logging.getLogger()
LOG.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

SIE_BASE_URL = os.environ.get(
    "SIE_BASE_URL", "https://www.banxico.org.mx/SieAPIRest/service/v1"
)
BRONZE_BUCKET = os.environ.get("BRONZE_BUCKET", "")
BRONZE_PREFIX = os.environ.get("BRONZE_PREFIX", "banxico_sie")
TOKEN_PARAM = os.environ.get("TOKEN_PARAMETER_NAME", "/fx-pricing/banxico/token")
SERIES = [s.strip() for s in os.environ.get("SERIES", "SF43718").split(",") if s.strip()]
MAX_ATTEMPTS = int(os.environ.get("MAX_ATTEMPTS", "4"))
BASE_BACKOFF_SECONDS = float(os.environ.get("BASE_BACKOFF_SECONDS", "2"))
HTTP_TIMEOUT_SECONDS = float(os.environ.get("HTTP_TIMEOUT_SECONDS", "10"))
METRIC_NAMESPACE = os.environ.get("METRIC_NAMESPACE", "FxPricing/Ingesta")

_s3 = None
_ssm = None
_token_cache = None


class TransientError(Exception):
    """Error que vale la pena reintentar (red, 5xx, 429)."""


class PayloadError(Exception):
    """La respuesta no tiene la estructura esperada del SIE."""


def _clients():
    global _s3, _ssm
    if _s3 is None:
        _s3 = boto3.client("s3")
    if _ssm is None:
        _ssm = boto3.client("ssm")
    return _s3, _ssm


def _get_token():
    """Lee el token de SSM Parameter Store (SecureString). Nunca se registra en logs."""
    global _token_cache
    if _token_cache is None:
        _, ssm = _clients()
        resp = ssm.get_parameter(Name=TOKEN_PARAM, WithDecryption=True)
        _token_cache = resp["Parameter"]["Value"]
    return _token_cache


def _http_get(url, token):
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "Bmx-Token": token,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_SECONDS) as resp:
            body = resp.read()
            if resp.headers.get("Content-Encoding") == "gzip":
                body = gzip.decompress(body)
            return resp.status, body
    except urllib.error.HTTPError as exc:
        if exc.code == 429 or exc.code >= 500:
            raise TransientError(f"HTTP {exc.code}") from exc
        # 4xx distinto de 429: token inválido, serie inexistente, etc. No se reintenta.
        raise
    except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
        raise TransientError(str(exc)) from exc


def fetch_with_retries(url, token, sleep=time.sleep):
    """GET con reintentos y espera incremental (exponencial): 2s, 4s, 8s..."""
    last_exc = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            status, body = _http_get(url, token)
            return status, body, attempt
        except TransientError as exc:
            last_exc = exc
            LOG.warning(json.dumps({"evento": "reintento", "intento": attempt, "error": str(exc)}))
            if attempt < MAX_ATTEMPTS:
                sleep(BASE_BACKOFF_SECONDS * (2 ** (attempt - 1)))
    raise TransientError(f"Agotados {MAX_ATTEMPTS} intentos: {last_exc}")


def _parse_fecha(fecha_sie):
    """El SIE entrega fechas como dd/mm/aaaa. Se devuelve aaaa-mm-dd."""
    return datetime.strptime(fecha_sie, "%d/%m/%Y").strftime("%Y-%m-%d")


def extract_observation_dates(body):
    """Validación MÍNIMA de estructura, solo para poder nombrar la llave en S3.

    Las validaciones de calidad completas (rangos, nulos, N/E, etc.) viven en la
    Lambda de validación; aquí solo se confirma que el payload es del SIE.
    """
    try:
        doc = json.loads(body)
        series = doc["bmx"]["series"]
        fechas = [_parse_fecha(d["fecha"]) for s in series for d in s.get("datos", [])]
    except (ValueError, KeyError, TypeError) as exc:
        raise PayloadError(f"Estructura inesperada: {exc}") from exc
    return fechas


def _exists_same_payload(s3, prefix, sha256_hex):
    """Idempotencia: ¿ya hay un objeto con este mismo contenido bajo el prefijo?"""
    resp = s3.list_objects_v2(Bucket=BRONZE_BUCKET, Prefix=prefix)
    for obj in resp.get("Contents", []):
        head = s3.head_object(Bucket=BRONZE_BUCKET, Key=obj["Key"])
        if head.get("Metadata", {}).get("sha256") == sha256_hex:
            return obj["Key"]
    return None


def _put_bronze(s3, key, body, metadata):
    s3.put_object(
        Bucket=BRONZE_BUCKET,
        Key=key,
        Body=body,
        ContentType="application/json",
        Metadata=metadata,
        ServerSideEncryption="AES256",
    )


def _emit_metric(name, value=1, **dims):
    """Métrica en formato EMF: CloudWatch la convierte en métrica sin llamadas extra."""
    print(json.dumps({
        "_aws": {
            "Timestamp": int(time.time() * 1000),
            "CloudWatchMetrics": [{
                "Namespace": METRIC_NAMESPACE,
                "Dimensions": [list(dims.keys())] if dims else [[]],
                "Metrics": [{"Name": name, "Unit": "Count"}],
            }],
        },
        name: value,
        **dims,
    }))


def ingest_series(serie, mode, run_id, captured_at, start=None, end=None, sleep=time.sleep):
    s3, _ = _clients()
    token = _get_token()

    if mode == "backfill":
        url = f"{SIE_BASE_URL}/series/{serie}/datos/{start}/{end}"
    else:
        url = f"{SIE_BASE_URL}/series/{serie}/datos/oportuno"

    status, body, attempts = fetch_with_retries(url, token, sleep=sleep)
    sha = hashlib.sha256(body).hexdigest()
    ts = captured_at.strftime("%Y%m%dT%H%M%SZ")
    metadata = {
        "sha256": sha,
        "run-id": run_id,
        "captured-at": captured_at.isoformat(),
        "serie": serie,
        "mode": mode,
        "http-status": str(status),
        "attempts": str(attempts),
        "source-url": url.replace(SIE_BASE_URL, "sie"),  # sin token
    }

    try:
        fechas = extract_observation_dates(body)
    except PayloadError:
        # Se conserva el original en cuarentena para analizarlo y reprocesar después.
        key = f"{BRONZE_PREFIX}/_cuarentena/serie={serie}/ingesta={ts}_{run_id[:8]}.json"
        _put_bronze(s3, key, body, metadata)
        _emit_metric("PayloadInvalido", serie=serie)
        raise

    if mode == "backfill":
        prefix = f"{BRONZE_PREFIX}/backfill/serie={serie}/rango={start}_{end}/"
    else:
        if not fechas:
            _emit_metric("SinNuevaPublicacion", serie=serie)
            return {"serie": serie, "resultado": "SIN_DATOS"}
        prefix = f"{BRONZE_PREFIX}/serie={serie}/fecha_dato={max(fechas)}/"

    existing = _exists_same_payload(s3, prefix, sha)
    if existing:
        _emit_metric("SinNuevaPublicacion", serie=serie)
        return {"serie": serie, "resultado": "SIN_NUEVA_PUBLICACION", "key": existing}

    key = f"{prefix}ingesta={ts}_{sha[:12]}.json"
    _put_bronze(s3, key, body, metadata)
    _emit_metric("IngestaExitosa", serie=serie)
    return {"serie": serie, "resultado": "GUARDADO", "key": key, "observaciones": len(fechas)}


def lambda_handler(event, context):
    if not BRONZE_BUCKET:
        raise RuntimeError("Falta la variable de entorno BRONZE_BUCKET")
    event = event or {}
    mode = event.get("mode", "daily")
    series = event.get("series") or SERIES
    run_id = getattr(context, "aws_request_id", None) or str(uuid.uuid4())
    captured_at = datetime.now(timezone.utc).replace(microsecond=0)

    results, errors = [], []
    for serie in series:
        try:
            results.append(ingest_series(
                serie, mode, run_id, captured_at,
                start=event.get("start"), end=event.get("end"),
            ))
        except Exception as exc:  # se registra y se sigue con la siguiente serie
            LOG.error(json.dumps({"evento": "fallo_serie", "serie": serie, "error": str(exc)}))
            _emit_metric("IngestaFallida", serie=serie)
            errors.append({"serie": serie, "error": str(exc)})

    summary = {"run_id": run_id, "mode": mode, "resultados": results, "errores": errors}
    LOG.info(json.dumps(summary))
    if errors:
        # Hacer fallar la invocación para que cuente en la métrica Errors -> alarma -> SNS.
        raise RuntimeError(f"Ingesta con errores: {errors}")
    return summary
