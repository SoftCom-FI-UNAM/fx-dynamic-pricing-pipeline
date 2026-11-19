"""Lambda validacion_calculo: bronze -> silver + gold (versión mínima para demo).

Se dispara con cada objeto nuevo en bronze (regla de EventBridge) o a mano:
  * Evento de S3 vía EventBridge: procesa ese objeto.
  * {"key": "banxico_sie/serie=.../x.json"}: procesa una llave concreta.
  * {"mode": "rebuild"}: toma el archivo más reciente de cada serie en bronze
    y reconstruye el estado vigente (útil para la primera vez o para reprocesar).

Qué hace:
  1. Valida el payload del SIE: estructura, fechas dd/mm/aaaa, valores numéricos,
     descarta "N/E" y valores fuera de rango plausible.
  2. Escribe cada observación válida en silver: JSON por serie y fecha, y el
     histórico acumulado en Parquet (silver/historico/serie=X/historico.parquet).
  3. Actualiza gold/risk/current.json con el último FIX, su variación diaria,
     media y desviación estándar de la ventana móvil, bandera de anomalía e inflación.
  4. Si el FIX nuevo se sale de media ± sigma·desv, publica alerta en SNS.
  5. Invoca (asíncrono) la evaluación del catálogo para recalcular márgenes con el FIX nuevo.

Parquet usa pandas + pyarrow de la capa administrada AWS SDK for pandas. Si la capa
no estuviera disponible, se registra un aviso y el resto del flujo sigue funcionando.
"""
import io
import json
import logging
import os
import statistics
import time
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError, ParamValidationError

LOG = logging.getLogger()
LOG.setLevel("INFO")

BRONZE_BUCKET = os.environ.get("BRONZE_BUCKET", "")
SILVER_BUCKET = os.environ.get("SILVER_BUCKET", "")
GOLD_BUCKET = os.environ.get("GOLD_BUCKET", "")
STATE_KEY = os.environ.get("STATE_KEY", "risk/current.json")
ALERTS_TOPIC_ARN = os.environ.get("ALERTS_TOPIC_ARN", "")
ANOMALY_WINDOW = int(os.environ.get("ANOMALY_WINDOW", "7"))
ANOMALY_SIGMA = float(os.environ.get("ANOMALY_SIGMA", "2"))
RULE_VERSION = os.environ.get("RULE_VERSION", "pending-client-approval")
CATALOG_EVAL_FUNCTION = os.environ.get("CATALOG_EVAL_FUNCTION", "")
PARQUET_PREFIX = os.environ.get("PARQUET_PREFIX", "historico")
BRONZE_PREFIX = "banxico_sie"

FX_SERIES = "SF43718"
INFLATION_SERIES = "SP30578"
# Rangos plausibles (configurables en la siguiente etapa con Finanzas).
PLAUSIBLE = {FX_SERIES: (5.0, 60.0), INFLATION_SERIES: (-10.0, 50.0)}
MIN_HISTORY_FOR_ANOMALY = 3

_s3 = None
_sns = None
_lambda = None


def _clients():
    global _s3, _sns, _lambda
    if _s3 is None:
        _s3 = boto3.client("s3")
        _sns = boto3.client("sns")
        _lambda = boto3.client("lambda")
    return _s3, _sns


def parse_payload(body):
    """Devuelve (observaciones_validas, rechazadas). Lanza ValueError si la estructura no es del SIE."""
    doc = json.loads(body)
    series = doc["bmx"]["series"]
    valid, rejected = [], []
    for s in series:
        serie = s.get("idSerie", "")
        for d in s.get("datos", []) or []:
            raw = str(d.get("dato", "")).replace(",", "").strip()
            try:
                fecha = datetime.strptime(d["fecha"], "%d/%m/%Y").strftime("%Y-%m-%d")
                value = float(raw)
            except (KeyError, ValueError):
                rejected.append({"serie": serie, "fecha": d.get("fecha"), "dato": d.get("dato"), "motivo": "no_numerico_o_fecha_invalida"})
                continue
            lo, hi = PLAUSIBLE.get(serie, (float("-inf"), float("inf")))
            if not lo <= value <= hi:
                rejected.append({"serie": serie, "fecha": fecha, "dato": value, "motivo": "fuera_de_rango"})
                continue
            valid.append({"serie": serie, "fecha": fecha, "valor": value})
    return valid, rejected


def compute_fx(history, window=ANOMALY_WINDOW, sigma=ANOMALY_SIGMA):
    """history: dict fecha->valor. Calcula indicadores sobre la observación más reciente."""
    dates = sorted(history)
    latest_date = dates[-1]
    latest = history[latest_date]
    prev = [history[d] for d in dates[:-1]][-window:]
    out = {
        "indicator_date": latest_date,
        "fx_fix_mxn_per_usd": latest,
        "fx_change_pct": None,
        "fx_window_size": len(prev),
        "fx_window_mean": None,
        "fx_window_std": None,
        "anomaly": False,
        "risk_status": "SIN_HISTORIAL_SUFICIENTE",
    }
    if prev:
        out["fx_change_pct"] = round((latest / prev[-1] - 1) * 100, 4)
    if len(prev) >= MIN_HISTORY_FOR_ANOMALY:
        mean = statistics.fmean(prev)
        std = statistics.pstdev(prev)
        out["fx_window_mean"] = round(mean, 4)
        out["fx_window_std"] = round(std, 6)
        out["anomaly"] = std > 0 and abs(latest - mean) > sigma * std
        out["risk_status"] = "ANOMALIA" if out["anomaly"] else "NORMAL"
    return out


def _read_state(s3):
    try:
        obj = s3.get_object(Bucket=GOLD_BUCKET, Key=STATE_KEY)
        return json.loads(obj["Body"].read()), obj.get("ETag")
    except ClientError as exc:
        if exc.response["Error"]["Code"] in ("NoSuchKey", "404"):
            return {}, None
        raise


def update_state(s3, mutate, attempts=5):
    """Lee-modifica-escribe current.json con If-Match: si otra Lambda escribió en medio
    (p. ej. FIX e inflación procesándose en paralelo), se vuelve a leer y se reintenta."""
    for i in range(attempts):
        state, etag = _read_state(s3)
        new_state = mutate(dict(state))
        kw = {"IfMatch": etag} if etag else {"IfNoneMatch": "*"}
        body = json.dumps(new_state, ensure_ascii=False, indent=2).encode()
        try:
            s3.put_object(Bucket=GOLD_BUCKET, Key=STATE_KEY, Body=body,
                          ContentType="application/json", ServerSideEncryption="AES256", **kw)
            return state, new_state
        except ParamValidationError:  # boto3 sin soporte de escritura condicional
            s3.put_object(Bucket=GOLD_BUCKET, Key=STATE_KEY, Body=body,
                          ContentType="application/json", ServerSideEncryption="AES256")
            return state, new_state
        except ClientError as exc:
            if exc.response["Error"]["Code"] in ("PreconditionFailed", "ConditionalRequestConflict", "412"):
                time.sleep(0.2 * (i + 1))
                continue
            raise
    raise RuntimeError("No se pudo actualizar el estado tras varios intentos (conflictos de escritura)")


def write_parquet_history(s3, serie, new_obs):
    """Fusiona las observaciones nuevas con el histórico Parquet de la serie (dedup por fecha)."""
    try:
        import pandas as pd  # capa AWS SDK for pandas
    except ImportError:
        LOG.warning(json.dumps({"evento": "parquet_omitido", "motivo": "pandas/pyarrow no disponible"}))
        return None
    key = f"{PARQUET_PREFIX}/serie={serie}/historico.parquet"
    new = pd.DataFrame(new_obs)[["serie", "fecha", "valor", "fuente_bronze", "capturado"]]
    try:
        old = pd.read_parquet(io.BytesIO(s3.get_object(Bucket=SILVER_BUCKET, Key=key)["Body"].read()))
        df = pd.concat([old, new], ignore_index=True)
    except ClientError as exc:
        if exc.response["Error"]["Code"] not in ("NoSuchKey", "404"):
            raise
        df = new
    df["fecha"] = pd.to_datetime(df["fecha"]).dt.date
    df["valor"] = df["valor"].astype("float64")
    df = df.drop_duplicates(subset=["fecha"], keep="last").sort_values("fecha").reset_index(drop=True)
    buf = io.BytesIO()
    df.to_parquet(buf, index=False, engine="pyarrow", compression="snappy")
    s3.put_object(Bucket=SILVER_BUCKET, Key=key, Body=buf.getvalue(),
                  ContentType="application/vnd.apache.parquet", ServerSideEncryption="AES256")
    return {"key": key, "filas": len(df)}


def _latest_keys(s3):
    """Llave más reciente de cada serie en bronze (las llaves ordenan por fecha e ingesta)."""
    keys = []
    for serie in (FX_SERIES, INFLATION_SERIES):
        best = None
        for page in s3.get_paginator("list_objects_v2").paginate(
            Bucket=BRONZE_BUCKET, Prefix=f"{BRONZE_PREFIX}/serie={serie}/"
        ):
            for o in page.get("Contents", []):
                if best is None or o["Key"] > best:
                    best = o["Key"]
        if best:
            keys.append(best)
    return keys


def _keys_from_event(event, s3):
    if event.get("mode") == "rebuild":
        return _latest_keys(s3)
    if event.get("key"):
        return [event["key"]]
    detail = event.get("detail") or {}
    key = (detail.get("object") or {}).get("key")
    return [key] if key else []


def process(keys, s3, sns):
    counts = {"entrada": 0, "aceptadas": 0, "rechazadas": 0}
    fx_obs, infl_obs, by_serie = {}, [], {}
    fx_captured = None

    for key in keys:
        obj = s3.get_object(Bucket=BRONZE_BUCKET, Key=key)
        meta = obj.get("Metadata", {})
        try:
            valid, rejected = parse_payload(obj["Body"].read())
        except (ValueError, KeyError, TypeError) as exc:
            LOG.error(json.dumps({"evento": "payload_invalido", "key": key, "error": str(exc)}))
            counts["rechazadas"] += 1
            continue
        counts["entrada"] += len(valid) + len(rejected)
        counts["aceptadas"] += len(valid)
        counts["rechazadas"] += len(rejected)
        for r in rejected:
            LOG.warning(json.dumps({"evento": "registro_rechazado", "key": key, **r}))

        for v in valid:
            rec = {**v, "fuente_bronze": key, "capturado": meta.get("captured-at")}
            s3.put_object(
                Bucket=SILVER_BUCKET,
                Key=f"banxico/serie={v['serie']}/fecha={v['fecha']}.json",
                Body=json.dumps(rec).encode(),
                ContentType="application/json",
                ServerSideEncryption="AES256",
            )
            by_serie.setdefault(v["serie"], []).append(rec)
            if v["serie"] == FX_SERIES:
                fx_obs[v["fecha"]] = v["valor"]
                if meta.get("captured-at") and meta.get("mode", "daily") == "daily":
                    fx_captured = meta["captured-at"]
            elif v["serie"] == INFLATION_SERIES:
                infl_obs.append(v)

    if counts["aceptadas"] == 0:
        # No se sobrescribe un estado válido si no hubo datos nuevos válidos.
        LOG.info(json.dumps({"evento": "sin_datos_validos", "keys": keys, **counts}))
        return {"status": "SIN_DATOS_VALIDOS", **counts}

    parquet = {}
    for serie, recs in by_serie.items():
        try:
            parquet[serie] = write_parquet_history(s3, serie, recs)
        except Exception as exc:  # el Parquet no debe tumbar el estado vigente
            LOG.error(json.dumps({"evento": "parquet_error", "serie": serie, "error": str(exc)}))

    def mutate(state):
        hist = {h["fecha"]: h["valor"] for h in state.get("fx_history", [])}
        hist.update(fx_obs)
        for v in infl_obs:
            if not state.get("inflation_date") or v["fecha"] >= state["inflation_date"]:
                state.update(inflation_value=v["valor"], inflation_date=v["fecha"])
        if hist:
            state.update(compute_fx(hist))
            keep = sorted(hist)[-(ANOMALY_WINDOW + 1):]
            state["fx_history"] = [{"fecha": d, "valor": hist[d]} for d in keep]
        if fx_captured:
            state["ingested_at"] = fx_captured
        state.setdefault("catalog_evaluation", "PENDING_CATALOG_EXPORT")
        if state["catalog_evaluation"] != "EVALUATED":
            # Sin catálogo evaluado, la recomendación sale solo del FIX; si hay catálogo,
            # la Lambda de evaluación recalcula promotion_action con los márgenes por SKU.
            state["promotion_action"] = "REVIEW_PRICES" if state.get("anomaly") else "NO_CHANGE"
        state.update({
            "processed_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "rule_version": RULE_VERSION,
            "anomaly_rule": f"|FIX - media| > {ANOMALY_SIGMA:g} desv. sobre {ANOMALY_WINDOW} observaciones",
        })
        return state

    old_state, new_state = update_state(s3, mutate)

    fx_changed = new_state.get("indicator_date") != old_state.get("indicator_date") or \
        new_state.get("fx_fix_mxn_per_usd") != old_state.get("fx_fix_mxn_per_usd")
    if new_state.get("anomaly") and fx_changed and ALERTS_TOPIC_ARN:
        sns.publish(
            TopicArn=ALERTS_TOPIC_ARN,
            Subject="FX Pricing: anomalia en el tipo de cambio FIX",
            Message=json.dumps({k: new_state.get(k) for k in (
                "indicator_date", "fx_fix_mxn_per_usd", "fx_change_pct",
                "fx_window_mean", "fx_window_std", "anomaly_rule")}, ensure_ascii=False, indent=2),
        )
    if fx_obs and CATALOG_EVAL_FUNCTION and _lambda is not None:
        _lambda.invoke(FunctionName=CATALOG_EVAL_FUNCTION, InvocationType="Event",
                       Payload=json.dumps({"origen": "validacion"}).encode())

    summary = {"status": "OK", "keys": keys, **counts,
               "risk_status": new_state.get("risk_status"),
               "indicator_date": new_state.get("indicator_date"),
               "parquet": parquet}
    LOG.info(json.dumps(summary))
    return summary


def lambda_handler(event, context):
    s3, sns = _clients()
    keys = _keys_from_event(event or {}, s3)
    if not keys:
        return {"status": "SIN_LLAVES", "detalle": "El evento no trae ningún objeto que procesar."}
    return process(keys, s3, sns)
