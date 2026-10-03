"""
config.py — Configuración central del gateway.

Toda la configuración se lee desde variables de entorno (.env).
Las credenciales se cargan como SecretStr: su valor real nunca aparece en
repr(), print() ni en trazas de error (OWASP LLM02).

Interruptores de mitigación: cada uno enciende o apaga un control, para
demostrar el comportamiento ANTES y DESPUÉS con el mismo código.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ── Proveedor upstream ──────────────────────────────────────────────
    provider: Literal["gemini", "mock"] = "mock"
    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-2.5-flash"
    upstream_timeout_s: float = 20.0
    max_output_tokens: int = 300           # techo de consumo por respuesta (LLM10)

    # Falla simulada del proveedor mock: ninguna | timeout | auth | malformada
    mock_falla: Literal["ninguna", "timeout", "auth", "malformada"] = "ninguna"

    # ── Clientes autorizados del gateway ───────────────────────────────
    # Formato: "alias1:key1,alias2:key2". Generar keys con tools/generar_api_key.py
    client_api_keys: SecretStr = SecretStr("")

    # ── Interruptores de mitigación (true = protección activa) ─────────
    mitigation_llm10: bool = True          # rate limit por API key de cliente
    mitigation_llm01: bool = True          # filtro de prompt injection + delimitación
    mitigation_llm07: bool = True          # canary + filtro de salida del system prompt
    mitigation_llm02: bool = True          # errores seguros + key fuera de la URL
    mitigation_safe_logging: bool = True   # logging con lista blanca (LLM02)

    # ── Parámetros de los controles ────────────────────────────────────
    rate_limit: str = "10/minute"
    max_prompt_chars: int = 2000
    max_body_bytes: int = 16_384
    log_hmac_key: SecretStr = SecretStr("cambia-esta-sal-en-tu-env")
    log_path: str = "logs/gateway.log"
    cors_origins: str = "http://localhost:5173"

    @property
    def clientes(self) -> dict[str, str]:
        """Devuelve {api_key: alias}. Solo se usa en memoria para autenticar."""
        resultado: dict[str, str] = {}
        for par in self.client_api_keys.get_secret_value().split(","):
            if ":" in par:
                alias, key = par.split(":", 1)
                if alias.strip() and key.strip():
                    resultado[key.strip()] = alias.strip()
        return resultado


@lru_cache
def get_settings() -> Settings:
    return Settings()
