"""
gemini.py — Adaptador para Google Gemini (API REST generateContent).

Basado en llamar_google() de session_5/backend/proveedores.py del curso
(Repo-Fundamentos-Arquitectura-LLM, prof. Andrés Rojas), con tres cambios:

1. La API key viaja en el header x-goog-api-key, no en la URL. El original
   usa params={"key": api_key}: cualquier error de httpx incluye la URL
   completa en su mensaje, así que la key termina en trazas o respuestas.
   Con MITIGATION_LLM02=false se reproduce el comportamiento original para
   demostrar esa fuga (usa una key FALSA en la demo).
2. El system prompt va en systemInstruction, separado del texto del usuario.
3. Los errores no caen silenciosamente a una respuesta simulada: se
   clasifican y se lanzan como ErrorProveedor (degradación controlada).
"""
from __future__ import annotations

import httpx

from app.providers.base import ErrorProveedor, ResultadoModelo, tokens_aprox

URL = "https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"


async def generar(system_prompt: str, texto_usuario: str, settings) -> ResultadoModelo:
    if settings.gemini_api_key is None:
        raise ErrorProveedor("auth", "GEMINI_API_KEY no configurada")
    key = settings.gemini_api_key.get_secret_value()
    modelo = settings.gemini_model

    cuerpo = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": texto_usuario}]}],
        "generationConfig": {"maxOutputTokens": settings.max_output_tokens, "temperature": 0.2},
    }
    if "2.5-flash" in modelo:
        # En 2.5 Flash el "thinking" consume tokens de salida; se desactiva
        # para que el techo de max_output_tokens se use en la respuesta.
        cuerpo["generationConfig"]["thinkingConfig"] = {"thinkingBudget": 0}

    if settings.mitigation_llm02:
        headers, params = {"x-goog-api-key": key}, None
    else:
        headers, params = {}, {"key": key}  # patrón original del curso (inseguro)

    try:
        async with httpx.AsyncClient(timeout=settings.upstream_timeout_s) as cliente:
            resp = await cliente.post(URL.format(modelo=modelo), headers=headers, params=params, json=cuerpo)
            resp.raise_for_status()
            data = resp.json()
    except httpx.TimeoutException as exc:
        raise ErrorProveedor("timeout", f"{type(exc).__name__}: {exc}") from None
    except httpx.HTTPStatusError as exc:
        codigo = exc.response.status_code
        tipo = "auth" if codigo in (400, 401, 403) else "cuota" if codigo == 429 else "no_disponible"
        raise ErrorProveedor(tipo, f"{exc} | cuerpo: {exc.response.text[:500]}") from None
    except httpx.HTTPError as exc:
        raise ErrorProveedor("no_disponible", f"{type(exc).__name__}: {exc}") from None

    try:
        texto = "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"])
    except (KeyError, IndexError, TypeError):
        raise ErrorProveedor("malformada", f"respuesta inesperada: {str(data)[:300]}") from None

    meta = data.get("usageMetadata", {})
    return ResultadoModelo(
        proveedor="gemini",
        modelo=modelo,
        texto=texto,
        tokens_entrada=meta.get("promptTokenCount", tokens_aprox(system_prompt + texto_usuario)),
        tokens_salida=meta.get("candidatesTokenCount", tokens_aprox(texto)),
    )
