"""Diagnóstico local: llama a Gemini igual que el gateway y muestra el error real.
Uso: python tools/diagnosticar_gemini.py   (no expone la key: viaja en el header)"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings
from app.providers import gemini
from app.providers.base import ErrorProveedor

s = get_settings()
print(f"Modelo: {s.gemini_model} | key cargada: {s.gemini_api_key is not None} | key en header: {s.mitigation_llm02}")
try:
    r = asyncio.run(gemini.generar("Eres un asistente de soporte de TI.", "Hola, prueba de conexion", s))
    print("OK ->", r.texto[:200])
except ErrorProveedor as e:
    print("ERROR tipo:", e.tipo)
    print("Detalle:", e.detalle_interno)