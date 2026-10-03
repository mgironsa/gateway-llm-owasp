"""
Fixtures comunes. Todas las pruebas usan el proveedor mock: son
reproducibles, offline y sin costo. `crear_cliente(...)` arma un gateway
con los interruptores que cada prueba necesita (antes / después).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

KEY_A = "test-key-cliente-a-0123456789abcdef"
KEY_B = "test-key-cliente-b-0123456789abcdef"
KEY_PROVEEDOR = "AIzaSyTEST-proveedor-0000-no-real"


@pytest.fixture
def crear_cliente(tmp_path):
    def _crear(**overrides):
        base = dict(
            provider="mock",
            gemini_api_key=KEY_PROVEEDOR,
            client_api_keys=f"cliente-a:{KEY_A},cliente-b:{KEY_B}",
            rate_limit="10/minute",
            log_path=str(tmp_path / "gateway.log"),
            log_hmac_key="sal-de-prueba",
        )
        base.update(overrides)
        settings = Settings(_env_file=None, **base)
        app = create_app(settings)
        return TestClient(app), settings

    return _crear


def chat(cliente: TestClient, mensaje: str, key: str = KEY_A):
    return cliente.post("/v1/chat", json={"mensaje": mensaje}, headers={"X-API-Key": key})
