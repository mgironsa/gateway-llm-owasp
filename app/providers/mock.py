"""
mock.py — Proveedor simulado, determinístico y DELIBERADAMENTE vulnerable.

Sirve para que las pruebas y los ataques sean reproducibles sin internet,
sin API key y sin costo: se comporta como un modelo ingenuo que obedece
inyecciones y repite su system prompt si se lo piden. Así la línea base
(mitigaciones apagadas) siempre "falla" de forma visible, y la diferencia
con las mitigaciones activas no depende del humor de un modelo real.

MOCK_FALLA simula errores del proveedor (timeout, auth, malformada) para
probar la degradación controlada.
"""
from __future__ import annotations

import re

from app.providers.base import ErrorProveedor, ResultadoModelo, tokens_aprox
from app.security.input_guard import normalizar

KEY_FALSA = "AIzaSyFAKE-0000-demo-no-es-real-0000"


async def generar(system_prompt: str, texto_usuario: str, settings) -> ResultadoModelo:
    key = settings.gemini_api_key.get_secret_value() if settings.gemini_api_key else KEY_FALSA
    url = "https://generativelanguage.googleapis.com/v1beta/models/mock:generateContent"
    url_visible = url if settings.mitigation_llm02 else f"{url}?key={key}"

    if settings.mock_falla == "timeout":
        raise ErrorProveedor("timeout", f"ReadTimeout: timed out calling '{url_visible}'")
    if settings.mock_falla == "auth":
        raise ErrorProveedor(
            "auth",
            f"Client error '400 Bad Request' for url '{url_visible}' | cuerpo: API key not valid",
        )
    if settings.mock_falla == "malformada":
        raise ErrorProveedor("malformada", "respuesta inesperada: {'candidates': []}")

    t = normalizar(texto_usuario)
    if re.search(r"\b(repite|repeat|muestra|imprime|revela|copia)\b.*\b(anterior|antes|above|instrucciones|inicial)\b", t):
        texto = f"Claro, este es el texto anterior: {system_prompt}"
    elif re.search(r"\b(ignora|ignore|olvida|disregard)\w*\b", t):
        texto = "Entendido, ignoro mis instrucciones anteriores. Nuevo rol aceptado: " + texto_usuario[-120:]
    else:
        texto = "[MOCK] Respuesta de soporte de TI para: " + texto_usuario[:120]

    return ResultadoModelo(
        proveedor="mock",
        modelo="mock-vulnerable",
        texto=texto,
        tokens_entrada=tokens_aprox(system_prompt + texto_usuario),
        tokens_salida=tokens_aprox(texto),
    )
