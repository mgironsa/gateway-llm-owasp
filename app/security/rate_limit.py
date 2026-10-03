"""
rate_limit.py — OWASP LLM10: Unbounded Consumption.

El límite se aplica POR API KEY DE CLIENTE, no por IP: en un gateway real
varios clientes pueden compartir IP (NAT, proxy corporativo) y un mismo
cliente puede cambiar de IP. Lo que se quiere acotar es el consumo de cada
cliente.

La key del cliente nunca se guarda en claro en el contador: se usa su hash.
Complementos de LLM10 en otros módulos: techo de max_output_tokens
(providers) y límites de tamaño del prompt y del cuerpo (main.py).
"""
from __future__ import annotations

import hashlib

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded

from app.auth import HEADER


def clave_por_cliente(request: Request) -> str:
    """key_func de slowapi: identifica al cliente por el hash de su API key."""
    key = request.headers.get(HEADER, "")
    return "cliente:" + hashlib.sha256(key.encode()).hexdigest()[:16]


def crear_limiter(habilitado: bool) -> Limiter:
    # enabled=False deja pasar todo: es la línea base SIN protección.
    return Limiter(key_func=clave_por_cliente, enabled=habilitado)


async def manejar_exceso(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    request.state.mitigacion = "LLM10"
    return JSONResponse(
        status_code=429,
        content={
            "error": "Límite de solicitudes excedido para este cliente. Intenta más tarde.",
            "request_id": getattr(request.state, "request_id", None),
        },
    )
