"""
logging_seguro.py — Registro de auditoría sin datos sensibles (OWASP LLM02).

Principio: LISTA BLANCA. Solo se escriben los campos de CAMPOS_PERMITIDOS;
cualquier otro campo se descarta antes de escribir. Es más seguro que una
lista negra, porque un campo nuevo que alguien agregue mañana queda fuera
por defecto.

Nunca se registran: el texto del prompt ni de la respuesta, API keys
(del cliente o del proveedor), el canary ni el system prompt, ni trazas
completas de error. Para correlacionar solicitudes sin guardar contenido se
registra la longitud del prompt y un HMAC-SHA256 con sal secreta (un hash
sin sal permitiría adivinar prompts cortos comparando hashes).

Con MITIGATION_SAFE_LOGGING=false se reproduce el error común "registrar
todo por si acaso", para demostrar por qué es una fuga.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
from pathlib import Path

try:  # python-json-logger >= 3
    from pythonjsonlogger.json import JsonFormatter
except ImportError:  # versiones anteriores
    from pythonjsonlogger.jsonlogger import JsonFormatter

CAMPOS_PERMITIDOS = {
    "request_id",
    "endpoint",
    "metodo",
    "status_code",
    "latencia_ms",
    "cliente_id",
    "mitigacion",
    "motivo",
    "proveedor",
    "modelo",
    "tokens_entrada",
    "tokens_salida",
    "longitud_prompt",
    "prompt_hmac",
    "tipo_error",
}


def crear_logger(ruta: str) -> logging.Logger:
    Path(ruta).parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(f"gateway::{ruta}")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not logger.handlers:
        handler = logging.FileHandler(ruta, encoding="utf-8")
        handler.setFormatter(JsonFormatter("%(asctime)s %(levelname)s %(message)s", rename_fields={"asctime": "timestamp"}))
        logger.addHandler(handler)
    return logger


def huella_prompt(texto: str, sal: str) -> str:
    return hmac.new(sal.encode(), texto.encode(), hashlib.sha256).hexdigest()[:16]


def registrar(logger: logging.Logger, evento: dict, seguro: bool) -> None:
    if seguro:
        evento = {k: v for k, v in evento.items() if k in CAMPOS_PERMITIDOS}
    logger.info("solicitud", extra=evento)
    for handler in logger.handlers:
        handler.flush()
