"""
errors.py — Degradación controlada ante fallos (requisito no funcional + LLM02).

Con MITIGATION_LLM02=true el cliente solo recibe un mensaje genérico y un
request_id para soporte; el tipo de error queda en el log. Nunca se
devuelven trazas, nombres de librerías, URLs ni mensajes del proveedor.

Con MITIGATION_LLM02=false se reproduce el patrón del backend del curso
(detail=f"Error ...: {e}"), que expone el detalle interno al cliente.
"""
from __future__ import annotations

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.providers.base import ErrorProveedor

MENSAJES = {
    "timeout": (504, "El servicio de IA no respondió a tiempo. Intenta nuevamente."),
    "auth": (503, "El servicio de IA no está disponible temporalmente."),
    "cuota": (503, "El servicio de IA no está disponible temporalmente."),
    "no_disponible": (503, "El servicio de IA no está disponible temporalmente."),
    "malformada": (502, "El servicio de IA devolvió una respuesta inválida."),
}


def _rid(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def respuesta_error_proveedor(request: Request, exc: ErrorProveedor) -> JSONResponse:
    request.state.evento["tipo_error"] = exc.tipo
    if not request.app.state.settings.mitigation_llm02:
        request.state.evento["detalle_interno"] = exc.detalle_interno
        return JSONResponse(status_code=502, content={"detail": f"Error al llamar al modelo: {exc.detalle_interno}"})
    codigo, mensaje = MENSAJES[exc.tipo]
    request.state.evento["mitigacion"] = "LLM02"
    return JSONResponse(status_code=codigo, content={"error": mensaje, "request_id": _rid(request)})


async def manejar_http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    # Los mensajes de HTTPException los escribe este código, no el usuario ni el proveedor.
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail, "request_id": _rid(request)})


async def manejar_validacion(request: Request, exc: RequestValidationError) -> JSONResponse:
    # La respuesta 422 por defecto de FastAPI repite el valor recibido ("input"),
    # lo que puede devolver datos sensibles. En modo seguro solo se indica el campo.
    if not request.app.state.settings.mitigation_llm02:
        return JSONResponse(status_code=422, content={"detail": exc.errors()})
    campos = sorted({".".join(str(p) for p in e.get("loc", [])[1:]) for e in exc.errors()})
    return JSONResponse(
        status_code=422,
        content={"error": "Solicitud inválida.", "campos": campos, "request_id": _rid(request)},
    )
