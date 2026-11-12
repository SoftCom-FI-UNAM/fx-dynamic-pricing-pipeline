"""Lambda consulta-riesgo: lee el estado vigente (JSON pequeño) en el bucket gold.

GET /v1/health        -> estado operativo básico.
GET /v1/risk/current  -> último estado publicado por la Lambda de validación.
Funciona con API Gateway (proxy) o invocación directa.
"""
import json
import os

import boto3

GOLD_BUCKET = os.environ.get("GOLD_BUCKET", "")
STATE_KEY = os.environ.get("STATE_KEY", "risk/current.json")
_s3 = boto3.client("s3")


def _response(status, body):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json", "Cache-Control": "no-store"},
        "body": json.dumps(body, ensure_ascii=False),
    }


def lambda_handler(event, context):
    path = (event or {}).get("rawPath") or (event or {}).get("path") or "/v1/risk/current"
    if path.endswith("/health"):
        return _response(200, {"status": "ok"})
    try:
        obj = _s3.get_object(Bucket=GOLD_BUCKET, Key=STATE_KEY)
        return _response(200, json.loads(obj["Body"].read()))
    except _s3.exceptions.NoSuchKey:
        return _response(503, {"status": "SIN_ESTADO", "detalle": "Aún no hay un estado calculado."})
