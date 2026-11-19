"""Lambda evaluacion_catalogo: cruza el FIX vigente con el export del catálogo.

Se dispara:
  * Cuando llega un export nuevo a catalog/exports/ (regla de EventBridge).
  * Cuando la Lambda de validación actualiza el estado vigente (invocación asíncrona).
  * A mano: {} usa el export más reciente; {"key": "exports/x.csv"} usa uno concreto.

Por cada SKU, con el FIX de hoy:
  costo_mxn       = unit_cost_usd * FIX
  margen_actual   = 1 - costo_mxn / recommended_price_mxn   (precio vigente publicado)
  * margen_actual >= margin_floor_pct            -> SIN_CAMBIO
  * si quitando la promoción se recupera el piso -> PAUSAR_PROMOCION (precio = base_usd * FIX)
  * si no                                        -> AJUSTAR_PRECIO   (precio = costo_mxn / (1 - piso))

Salidas:
  * gold/risk/current.json: SOLO resumen agregado (lo lee la API pública).
  * gold/catalog/evaluacion/latest.json: detalle por SKU (privado: la API no tiene permiso).
  * SNS si hay SKUs con margen negativo (una vez por fecha de FIX y export).
"""
import csv
import io
import json
import logging
import os
import time
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError, ParamValidationError

LOG = logging.getLogger()
LOG.setLevel("INFO")

CATALOG_BUCKET = os.environ.get("CATALOG_BUCKET", "")
CATALOG_PREFIX = os.environ.get("CATALOG_PREFIX", "exports/")
GOLD_BUCKET = os.environ.get("GOLD_BUCKET", "")
STATE_KEY = os.environ.get("STATE_KEY", "risk/current.json")
DETAIL_KEY = os.environ.get("DETAIL_KEY", "catalog/evaluacion/latest.json")
ALERTS_TOPIC_ARN = os.environ.get("ALERTS_TOPIC_ARN", "")
REQUIRED = ["sku", "category", "base_price_usd", "unit_cost_usd",
            "margin_floor_pct", "promo_discount_pct", "recommended_price_mxn"]

_s3 = None
_sns = None


def _clients():
    global _s3, _sns
    if _s3 is None:
        _s3 = boto3.client("s3")
        _sns = boto3.client("sns")
    return _s3, _sns


# --------------------------------------------------------------- estado con escritura condicional
def _read_state(s3):
    try:
        obj = s3.get_object(Bucket=GOLD_BUCKET, Key=STATE_KEY)
        return json.loads(obj["Body"].read()), obj.get("ETag")
    except ClientError as exc:
        if exc.response["Error"]["Code"] in ("NoSuchKey", "404"):
            return {}, None
        raise


def update_state(s3, mutate, attempts=5):
    """Lee-modifica-escribe current.json con If-Match para no pisar a otra Lambda."""
    for i in range(attempts):
        state, etag = _read_state(s3)
        new_state = mutate(dict(state))
        if new_state is None:
            return state
        kw = {"IfMatch": etag} if etag else {"IfNoneMatch": "*"}
        body = json.dumps(new_state, ensure_ascii=False, indent=2).encode()
        try:
            s3.put_object(Bucket=GOLD_BUCKET, Key=STATE_KEY, Body=body,
                          ContentType="application/json", ServerSideEncryption="AES256", **kw)
            return new_state
        except ParamValidationError:  # boto3 sin soporte de escritura condicional
            s3.put_object(Bucket=GOLD_BUCKET, Key=STATE_KEY, Body=body,
                          ContentType="application/json", ServerSideEncryption="AES256")
            return new_state
        except ClientError as exc:
            if exc.response["Error"]["Code"] in ("PreconditionFailed", "ConditionalRequestConflict", "412"):
                time.sleep(0.2 * (i + 1))
                continue
            raise
    raise RuntimeError("No se pudo actualizar el estado tras varios intentos (conflictos de escritura)")


# --------------------------------------------------------------- lógica de negocio
def _f(row, k):
    return float(str(row[k]).replace(",", "").strip())


def evaluate_row(row, fx):
    base = _f(row, "base_price_usd")
    cost_usd = _f(row, "unit_cost_usd")
    floor = _f(row, "margin_floor_pct")
    promo = _f(row, "promo_discount_pct")
    price = _f(row, "recommended_price_mxn")
    if price <= 0 or cost_usd < 0 or not 0 <= floor < 1 or not 0 <= promo < 1:
        raise ValueError("valores fuera de rango")
    cost_mxn = cost_usd * fx
    margin = 1 - cost_mxn / price
    out = {
        "sku": row["sku"].strip(), "category": row["category"].strip(),
        "precio_vigente_mxn": round(price, 2), "costo_mxn_hoy": round(cost_mxn, 2),
        "margen_actual": round(margin, 4), "margen_minimo": floor, "promo_discount_pct": promo,
    }
    if margin >= floor:
        out.update(accion="SIN_CAMBIO", precio_sugerido_mxn=round(price, 2))
    else:
        price_no_promo = base * fx
        if promo > 0 and 1 - cost_mxn / price_no_promo >= floor:
            out.update(accion="PAUSAR_PROMOCION", precio_sugerido_mxn=round(price_no_promo, 2))
        else:
            out.update(accion="AJUSTAR_PRECIO", precio_sugerido_mxn=round(cost_mxn / (1 - floor), 2))
    out["margen_negativo"] = margin < 0
    return out


def evaluate_catalog(csv_text, fx):
    reader = csv.DictReader(io.StringIO(csv_text))
    missing = [c for c in REQUIRED if c not in (reader.fieldnames or [])]
    if missing:
        raise ValueError(f"Faltan columnas en el export: {missing}")
    rows, rejected, seen = [], [], set()
    for i, row in enumerate(reader, start=2):
        sku = (row.get("sku") or "").strip()
        if not sku or sku in seen:
            rejected.append({"linea": i, "sku": sku, "motivo": "sku_vacio_o_duplicado"})
            continue
        try:
            rows.append(evaluate_row(row, fx))
            seen.add(sku)
        except (ValueError, TypeError) as exc:
            rejected.append({"linea": i, "sku": sku, "motivo": f"cuarentena: {exc}"})
    return rows, rejected


def summarize(rows, rejected):
    count = lambda a: sum(1 for r in rows if r["accion"] == a)  # noqa: E731
    by_cat = {}
    for r in rows:
        c = by_cat.setdefault(r["category"], {"skus": 0, "en_riesgo": 0})
        c["skus"] += 1
        c["en_riesgo"] += r["accion"] != "SIN_CAMBIO"
    pausar, ajustar = count("PAUSAR_PROMOCION"), count("AJUSTAR_PRECIO")
    return {
        "skus_evaluados": len(rows),
        "skus_rechazados": len(rejected),
        "skus_sin_cambio": count("SIN_CAMBIO"),
        "skus_pausar_promocion": pausar,
        "skus_ajustar_precio": ajustar,
        "skus_margen_negativo": sum(r["margen_negativo"] for r in rows),
        "por_categoria": by_cat,
    }, ("ADJUST_PRICES" if ajustar else "PAUSE_PROMOTIONS" if pausar else "NO_CHANGE")


def _latest_export(s3):
    best = None
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=CATALOG_BUCKET, Prefix=CATALOG_PREFIX):
        for o in page.get("Contents", []):
            if o["Key"].lower().endswith(".csv") and (best is None or o["LastModified"] > best["LastModified"]):
                best = o
    return best["Key"] if best else None


def lambda_handler(event, context):
    s3, sns = _clients()
    event = event or {}
    key = event.get("key") or ((event.get("detail") or {}).get("object") or {}).get("key")
    if key and not key.lower().endswith(".csv"):
        # p. ej. el objeto vacío "exports/" que crea la consola al hacer una carpeta
        LOG.info(json.dumps({"evento": "objeto_ignorado", "key": key}))
        return {"status": "IGNORADO", "key": key}
    key = key or _latest_export(s3)
    state, _ = _read_state(s3)
    fx, fx_date = state.get("fx_fix_mxn_per_usd"), state.get("indicator_date")

    if not key:
        update_state(s3, lambda st: {**st, "catalog_evaluation": "PENDING_CATALOG_EXPORT"})
        return {"status": "SIN_EXPORT"}
    if not fx:
        return {"status": "SIN_FIX", "detalle": "Aún no hay FIX en el estado vigente."}

    csv_text = s3.get_object(Bucket=CATALOG_BUCKET, Key=key)["Body"].read().decode("utf-8-sig")
    try:
        rows, rejected = evaluate_catalog(csv_text, fx)
    except ValueError as exc:
        # Un export inválido es un problema de datos: no se reintenta (no se lanza la excepción)
        # y solo marca el estado si es el export más reciente, para no tapar una evaluación válida.
        LOG.error(json.dumps({"evento": "export_invalido", "key": key, "error": str(exc)}, ensure_ascii=False))
        if key == _latest_export(s3):
            update_state(s3, lambda st: {**st, "catalog_evaluation": "EXPORT_INVALIDO"})
        if ALERTS_TOPIC_ARN:
            sns.publish(TopicArn=ALERTS_TOPIC_ARN, Subject="FX Pricing: export de catalogo invalido",
                        Message=json.dumps({"export": key, "error": str(exc)}, ensure_ascii=False))
        return {"status": "EXPORT_INVALIDO", "export": key, "error": str(exc)}
    summary, action = summarize(rows, rejected)
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    s3.put_object(
        Bucket=GOLD_BUCKET, Key=DETAIL_KEY, ContentType="application/json", ServerSideEncryption="AES256",
        Body=json.dumps({"evaluado": now, "fx_usado": fx, "indicator_date": fx_date, "export": key,
                         "resumen": summary, "skus": rows, "rechazados": rejected},
                        ensure_ascii=False, indent=2).encode(),
    )

    alert_id = f"{fx_date}|{key}"
    flags = {}

    def mutate(st):
        if st.get("indicator_date") != fx_date:
            return None  # llegó un FIX más nuevo: la validación volverá a invocarnos
        flags["alert"] = summary["skus_margen_negativo"] > 0 and st.get("catalog_alerted_for") != alert_id
        st.update({
            "catalog_evaluation": "EVALUATED",
            "catalog_export": key.rsplit("/", 1)[-1],
            "catalog_evaluated_at": now,
            "catalog_fx_used": fx,
            "catalog_summary": summary,
            "promotion_action": action,
        })
        if flags["alert"]:
            st["catalog_alerted_for"] = alert_id
        return st

    update_state(s3, mutate)
    if flags.get("alert") and ALERTS_TOPIC_ARN:
        sns.publish(
            TopicArn=ALERTS_TOPIC_ARN,
            Subject="FX Pricing: SKUs con margen negativo",
            Message=json.dumps({"indicator_date": fx_date, "fx": fx, "export": key,
                                "accion_sugerida": action, **summary}, ensure_ascii=False, indent=2),
        )
    result = {"status": "OK", "export": key, "fx": fx, "promotion_action": action, **summary}
    LOG.info(json.dumps(result, ensure_ascii=False))
    return result
