"""Genera una API key aleatoria para un cliente del gateway.

Uso:  python tools/generar_api_key.py
Copia el resultado en CLIENT_API_KEYS de tu .env (nunca en el código).
"""
import secrets

print("gw_" + secrets.token_urlsafe(32))
