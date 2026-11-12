"""Lambda validacion_calculo — ESQUELETO. Pendiente de implementar en la siguiente etapa.

Ya tiene permisos, variables de entorno y disparador configurados por
infra/Lambdas.yaml. Solo registra el evento recibido para comprobar
que el flujo de punta a punta funciona.
"""
import json
import logging
import os

LOG = logging.getLogger()
LOG.setLevel("INFO")


def lambda_handler(event, context):
    LOG.info(json.dumps({"evento_recibido": event, "config": {
        k: v for k, v in os.environ.items() if k.isupper() and not k.startswith("AWS")
    }}, default=str))
    return {"status": "PENDIENTE_DE_IMPLEMENTAR"}
