"""
base.py — Contrato común de los proveedores upstream.

Todo proveedor devuelve ResultadoModelo o lanza ErrorProveedor. El tipo de
error decide qué ve el cliente (errors.py); el detalle interno solo se usa
en el modo SIN protección, para demostrar la fuga.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

TipoError = Literal["timeout", "auth", "cuota", "no_disponible", "malformada"]


@dataclass
class ResultadoModelo:
    proveedor: str
    modelo: str
    texto: str
    tokens_entrada: int
    tokens_salida: int


class ErrorProveedor(Exception):
    def __init__(self, tipo: TipoError, detalle_interno: str):
        super().__init__(tipo)
        self.tipo = tipo
        self.detalle_interno = detalle_interno


def tokens_aprox(texto: str) -> int:
    """~4 caracteres por token (misma aproximación que el material del curso)."""
    return max(1, round(len(texto) / 4))
