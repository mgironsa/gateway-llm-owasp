"""
input_guard.py — OWASP LLM01: Prompt Injection.

Dos capas, aplicadas ANTES de que el texto llegue al modelo:

1. Detección: normaliza el texto (NFKC, sin caracteres invisibles, sin
   tildes, minúsculas, espacios colapsados) y lo compara contra patrones
   conocidos de inyección en español e inglés. Si hay coincidencia, la
   solicitud se rechaza y el texto NUNCA se envía al proveedor.
2. Delimitación: el texto que sí pasa se envuelve en <entrada_usuario>, y
   el system prompt indica tratar ese bloque como datos, no como órdenes.

LÍMITE CONOCIDO (documentado a propósito): un filtro de patrones no detiene
toda inyección. Paráfrasis nuevas, otros idiomas, codificaciones (base64) o
inyección indirecta desde documentos pueden pasar. Por eso la delimitación
es una segunda capa, y un clasificador dedicado (ej. Prompt Guard) sería
la siguiente mejora.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# Caracteres de ancho cero y de control de dirección: se usan para partir
# palabras clave ("ig\u200bnora") y burlar filtros ingenuos.
_INVISIBLES = re.compile(r"[\u200b-\u200f\u202a-\u202e\u2060-\u2064\ufeff\u00ad]")

PATRONES: list[tuple[str, re.Pattern]] = [
    ("ignorar_instrucciones_es", re.compile(r"\b(ignora|ignorar|ignore)\w*\b.{0,40}\b(instrucciones|indicaciones|reglas|anteriores|previas)\b")),
    ("ignorar_instrucciones_en", re.compile(r"\b(ignore|disregard|forget)\b.{0,40}\b(instructions|rules|previous|prior|above)\b")),
    ("olvidar_instrucciones_es", re.compile(r"\b(olvida|olvidate|descarta|omite)\w*\b.{0,40}\b(instrucciones|reglas|indicaciones|anterior\w*)\b")),
    ("mencion_system_prompt", re.compile(r"\b(system prompt|prompt (de|del) sistema|instrucciones (de|del) sistema|mensaje (de|del) sistema|instrucciones internas)\b")),
    ("extraer_texto_previo", re.compile(r"\b(repite|repeat|muestra|imprime|print|reveal|revela|copia|escribe)\b.{0,60}\b(anterior|antes|above|previo|before|inicial|original|todo lo que)\b")),
    ("cambio_de_rol", re.compile(r"\b(actua|act|comportate|pretend|finge|eres ahora|you are now)\b.{0,40}\b(sin restricciones|unrestricted|dan|modo desarrollador|developer mode|sin filtros)\b")),
    ("jailbreak_conocido", re.compile(r"\b(jailbreak|developer mode|modo desarrollador|dan mode)\b")),
    ("nuevas_instrucciones", re.compile(r"\b(nuevas instrucciones|new instructions)\s*:")),
    ("marcadores_de_rol", re.compile(r"(<\|?\s*/?\s*(system|im_start|im_end|entrada_usuario)\s*\|?>|\[/?inst\]|#{2,}\s*(system|sistema))")),
]


@dataclass
class ResultadoGuard:
    bloqueado: bool
    motivo: str | None
    texto: str


def normalizar(texto: str) -> str:
    """Forma canónica usada SOLO para comparar (el texto original no se altera)."""
    t = unicodedata.normalize("NFKC", texto)
    t = _INVISIBLES.sub("", t)
    t = "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")
    t = re.sub(r"\s+", " ", t).strip().lower()
    return t


def revisar_entrada(texto: str) -> ResultadoGuard:
    limpio = _INVISIBLES.sub("", unicodedata.normalize("NFKC", texto))
    canonico = normalizar(texto)
    for nombre, patron in PATRONES:
        if patron.search(canonico):
            return ResultadoGuard(bloqueado=True, motivo=nombre, texto=limpio)
    return ResultadoGuard(bloqueado=False, motivo=None, texto=limpio)


def delimitar(texto: str) -> str:
    """Envuelve el texto del usuario como datos. Quita cualquier etiqueta que
    intente cerrar o abrir el delimitador desde dentro."""
    sin_etiquetas = re.sub(r"</?\s*entrada_usuario\s*>", "", texto, flags=re.IGNORECASE)
    return f"<entrada_usuario>\n{sin_etiquetas}\n</entrada_usuario>"
