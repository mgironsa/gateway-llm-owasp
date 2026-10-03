"""
auth.py — Autenticación de clientes del gateway por header X-API-Key.

Es requisito para que el rate limiting sea POR CLIENTE y no por IP (LLM10).
La comparación usa hmac.compare_digest para no filtrar información por tiempo.
"""
from __future__ import annotations

import hmac

from fastapi import HTTPException, Request

HEADER = "X-API-Key"


def autenticar(request: Request) -> str:
    """Valida la API key del cliente y devuelve su alias (ej. 'cliente-a')."""
    settings = request.app.state.settings
    recibida = request.headers.get(HEADER, "")
    alias_encontrado = None
    for key, alias in settings.clientes.items():
        if recibida and hmac.compare_digest(recibida.encode(), key.encode()):
            alias_encontrado = alias
    if alias_encontrado is None:
        request.state.cliente_id = "anonimo"
        raise HTTPException(status_code=401, detail="API key de cliente inválida o ausente")
    request.state.cliente_id = alias_encontrado
    return alias_encontrado
