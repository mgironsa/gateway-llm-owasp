"""
output_guard.py — OWASP LLM07: System Prompt Leakage.

Revisa la respuesta del modelo ANTES de devolverla al cliente:

1. Canary: si la respuesta contiene la marca aleatoria que solo existe en
   el system prompt, hubo filtración.
2. Solapamiento: si la respuesta copia una secuencia de 6 o más palabras
   seguidas del system prompt (comparadas en forma normalizada), también
   se considera filtración, aunque el modelo haya omitido el canary.

Si detecta filtración, reemplaza la respuesta por un mensaje neutro. Ni el
canary ni el system prompt se escriben nunca en los logs.

LÍMITE CONOCIDO: una paráfrasis del system prompt (mismo contenido con
otras palabras) no se detecta. Por eso el system prompt no debe contener
secretos reales: la defensa principal es no poner ahí nada crítico.
"""
from __future__ import annotations

import secrets

from app.security.input_guard import normalizar

VENTANA_PALABRAS = 6
RESPUESTA_NEUTRA = "No puedo compartir información sobre mi configuración interna. ¿En qué tema de soporte de TI te ayudo?"


def generar_canary() -> str:
    return "CNRY-" + secrets.token_hex(8)


def _ngramas(texto: str, n: int) -> set[tuple[str, ...]]:
    palabras = normalizar(texto).split()
    return {tuple(palabras[i : i + n]) for i in range(len(palabras) - n + 1)}


def detectar_filtracion(respuesta: str, system_prompt: str, canary: str) -> str | None:
    """Devuelve el motivo de la filtración o None si la respuesta es segura."""
    if canary.lower() in respuesta.lower():
        return "canary_en_respuesta"
    if _ngramas(respuesta, VENTANA_PALABRAS) & _ngramas(system_prompt, VENTANA_PALABRAS):
        return "copia_del_system_prompt"
    return None
