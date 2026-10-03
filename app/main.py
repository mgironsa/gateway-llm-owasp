"""
main.py — Gateway LLM con seguridad OWASP Top 10 for LLM Applications (2025).

Punto único de entrada: POST /v1/chat. Ninguna otra parte del sistema
llama al proveedor. Orden de los controles en cada solicitud:

  1. Tamaño del cuerpo                     (LLM10, middleware)
  2. Autenticación X-API-Key               (auth.py)
  3. Rate limit por cliente                (LLM10, security/rate_limit.py)
  4. Tamaño del prompt                     (LLM10)
  5. Filtro de inyección + delimitación    (LLM01, security/input_guard.py)
  6. Llamada al proveedor con max tokens   (providers/)
  7. Filtro de filtración del system prompt (LLM07, security/output_guard.py)
  8. Registro de auditoría con lista blanca (LLM02, logging_seguro.py)

Ejecutar:  uvicorn app.main:app --port 8000
"""
from __future__ import annotations

import time
import uuid

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import errors
from app.auth import HEADER, autenticar
from app.config import Settings, get_settings
from app.logging_seguro import crear_logger, huella_prompt, registrar
from app.prompts import construir_system_prompt
from app.providers import gemini, mock
from app.providers.base import ErrorProveedor
from app.security import input_guard, output_guard
from app.security.rate_limit import crear_limiter, manejar_exceso

MENSAJE_RECHAZO_LLM01 = "La solicitud fue rechazada por la política de seguridad del gateway."


class SolicitudChat(BaseModel):
    mensaje: str = Field(..., min_length=1)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="Gateway LLM OWASP", version="1.0.0", docs_url="/docs")

    app.state.settings = settings
    app.state.canary = output_guard.generar_canary()
    app.state.system_prompt = construir_system_prompt(
        app.state.canary, llm01=settings.mitigation_llm01, llm07=settings.mitigation_llm07
    )
    app.state.logger = crear_logger(settings.log_path)
    app.state.proveedor = gemini if settings.provider == "gemini" else mock

    limiter = crear_limiter(settings.mitigation_llm10)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, manejar_exceso)
    app.add_exception_handler(StarletteHTTPException, errors.manejar_http)
    app.add_exception_handler(RequestValidationError, errors.manejar_validacion)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
        allow_methods=["POST", "GET"],
        allow_headers=["Content-Type", HEADER],
    )

    @app.middleware("http")
    async def auditoria(request: Request, call_next):
        inicio = time.perf_counter()
        request.state.request_id = uuid.uuid4().hex[:12]
        request.state.evento = {
            "request_id": request.state.request_id,
            "endpoint": request.url.path,
            "metodo": request.method,
        }
        if not settings.mitigation_safe_logging:
            # Error común a propósito: registrar headers completos "por si acaso".
            request.state.evento["headers"] = dict(request.headers)

        largo = request.headers.get("content-length")
        if settings.mitigation_llm10 and largo and int(largo) > settings.max_body_bytes:
            respuesta = JSONResponse(
                status_code=413,
                content={"error": "Solicitud demasiado grande.", "request_id": request.state.request_id},
            )
            request.state.evento["mitigacion"] = "LLM10"
            request.state.evento["motivo"] = "cuerpo_excede_limite"
        else:
            try:
                respuesta = await call_next(request)
            except Exception as exc:  # último recurso: nada interno llega al cliente
                request.state.evento["tipo_error"] = type(exc).__name__
                contenido = (
                    {"error": "Error interno del gateway.", "request_id": request.state.request_id}
                    if settings.mitigation_llm02
                    else {"detail": f"Error interno: {exc!r}"}
                )
                respuesta = JSONResponse(status_code=500, content=contenido)

        evento = request.state.evento
        evento["status_code"] = respuesta.status_code
        evento["latencia_ms"] = round((time.perf_counter() - inicio) * 1000, 1)
        evento["cliente_id"] = getattr(request.state, "cliente_id", "anonimo")
        if getattr(request.state, "mitigacion", None):
            evento["mitigacion"] = request.state.mitigacion
        registrar(app.state.logger, evento, seguro=settings.mitigation_safe_logging)
        return respuesta

    @app.get("/health")
    async def health():
        return {"estado": "ok"}

    @app.get("/v1/estado")
    async def estado(cliente: str = Depends(autenticar)):
        """Muestra qué mitigaciones están activas (útil para el video). Sin secretos."""
        return {
            "proveedor": settings.provider,
            "modelo": settings.gemini_model if settings.provider == "gemini" else "mock-vulnerable",
            "mitigaciones": {
                "LLM10_rate_limit": settings.mitigation_llm10,
                "LLM01_input_guard": settings.mitigation_llm01,
                "LLM07_output_guard": settings.mitigation_llm07,
                "LLM02_errores_seguros": settings.mitigation_llm02,
                "LLM02_logging_seguro": settings.mitigation_safe_logging,
            },
            "rate_limit": settings.rate_limit if settings.mitigation_llm10 else None,
        }

    @app.post("/v1/chat")
    @limiter.limit(settings.rate_limit)
    async def chat(request: Request, solicitud: SolicitudChat, cliente: str = Depends(autenticar)):
        evento = request.state.evento
        texto = solicitud.mensaje
        evento["longitud_prompt"] = len(texto)
        evento["prompt_hmac"] = huella_prompt(texto, settings.log_hmac_key.get_secret_value())
        if not settings.mitigation_safe_logging:
            evento["prompt"] = texto

        # LLM10: el consumo también crece con el tamaño del prompt, no solo con el número de solicitudes.
        if settings.mitigation_llm10 and len(texto) > settings.max_prompt_chars:
            evento.update(mitigacion="LLM10", motivo="prompt_excede_limite")
            return JSONResponse(
                status_code=413,
                content={"error": f"El mensaje supera {settings.max_prompt_chars} caracteres.", "request_id": request.state.request_id},
            )

        # LLM01: detección y delimitación antes de que el texto llegue al modelo.
        if settings.mitigation_llm01:
            resultado = input_guard.revisar_entrada(texto)
            if resultado.bloqueado:
                evento.update(mitigacion="LLM01", motivo=resultado.motivo)
                return JSONResponse(
                    status_code=400,
                    content={"error": MENSAJE_RECHAZO_LLM01, "request_id": request.state.request_id},
                )
            texto_modelo = input_guard.delimitar(resultado.texto)
        else:
            texto_modelo = texto

        try:
            r = await app.state.proveedor.generar(app.state.system_prompt, texto_modelo, settings)
        except ErrorProveedor as exc:
            return errors.respuesta_error_proveedor(request, exc)

        evento.update(proveedor=r.proveedor, modelo=r.modelo, tokens_entrada=r.tokens_entrada, tokens_salida=r.tokens_salida)
        texto_respuesta = r.texto

        # LLM07: la respuesta se revisa antes de salir del gateway.
        if settings.mitigation_llm07:
            motivo = output_guard.detectar_filtracion(texto_respuesta, app.state.system_prompt, app.state.canary)
            if motivo:
                evento.update(mitigacion="LLM07", motivo=motivo)
                texto_respuesta = output_guard.RESPUESTA_NEUTRA

        if not settings.mitigation_safe_logging:
            evento["respuesta"] = texto_respuesta

        return {
            "respuesta": texto_respuesta,
            "request_id": request.state.request_id,
            "modelo": r.modelo,
            "tokens": {"entrada": r.tokens_entrada, "salida": r.tokens_salida},
        }

    return app


app = create_app()
