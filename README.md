# Gateway LLM con Seguridad de Nivel Producción

Proyecto final · Opción 4 · Fundamentos de Arquitectura LLM (BSG Institute)

Gateway FastAPI que es el **único punto de entrada** (`POST /v1/chat`) entre las aplicaciones y el proveedor LLM (Google Gemini). Implementa y demuestra cuatro categorías del **OWASP Top 10 for LLM Applications (2025)**: LLM10, LLM01, LLM07 y LLM02. Cada mitigación se enciende o apaga con una variable de entorno, para mostrar el comportamiento antes y después con el mismo código.

El mapeo completo categoría → mitigación → evidencia está en [`docs/MAPEO_OWASP.md`](docs/MAPEO_OWASP.md).

## Estructura

```
app/
  main.py               único endpoint /v1/chat y orden de los controles
  config.py             configuración, SecretStr e interruptores
  auth.py               autenticación por X-API-Key
  prompts.py            system prompt con canary
  errors.py             degradación controlada (LLM02)
  logging_seguro.py     logs JSON con lista blanca (LLM02)
  security/
    rate_limit.py       LLM10
    input_guard.py      LLM01
    output_guard.py     LLM07
  providers/
    gemini.py           proveedor real (adaptado del material del curso)
    mock.py             proveedor simulado y vulnerable, para pruebas offline
attacks/                scripts de ataque que generan la evidencia
tests/                  29 pruebas pytest, antes y después de cada mitigación
docs/MAPEO_OWASP.md     entregable central
docs/evidencia/         salidas antes/ y despues/
```

## Instalación (Windows 11, PowerShell)

Requisitos: Python 3.12, Git y gitleaks.

```powershell
cd C:\dev\gateway-llm-owasp
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pre-commit install
copy .env.example .env
```

Genera tres valores con `python tools/generar_api_key.py` (ejecútalo tres veces) y complétalos en `.env`:

- `CLIENT_API_KEYS=cliente-a:<key1>,cliente-b:<key2>`
- `LOG_HMAC_KEY=<key3>`
- `GEMINI_API_KEY=<tu key de Google AI Studio>`, solo si usarás `PROVIDER=gemini`.

## Ejecutar

```powershell
# Terminal 1: el gateway
.venv\Scripts\Activate.ps1
uvicorn app.main:app --port 8000

# Terminal 2: pruebas y ataques
.venv\Scripts\Activate.ps1
python -m pytest -v
$env:GATEWAY_KEY_A = "<key de cliente-a>"
$env:GATEWAY_KEY_B = "<key de cliente-b>"
curl.exe -s http://localhost:8000/v1/estado -H "X-API-Key: $env:GATEWAY_KEY_A"
```

Documentación interactiva de la API: http://localhost:8000/docs

## Reproducir la evidencia antes/después

El gateway lee `.env` al arrancar: **después de cambiar un interruptor, reinicia uvicorn** (Ctrl+C y volver a ejecutar). Borra `logs\gateway.log` antes de cada corrida para que la evidencia de logs sea limpia.

| Categoría | Configuración en `.env` | Comando |
| --- | --- | --- |
| LLM01 antes | `MITIGATION_LLM01=false` | `python attacks/atacar.py llm01 --etiqueta antes` |
| LLM01 después | `MITIGATION_LLM01=true` | `python attacks/atacar.py llm01 --etiqueta despues` |
| LLM07 antes | `MITIGATION_LLM01=false`, `MITIGATION_LLM07=false` | `python attacks/atacar.py llm07 --etiqueta antes` |
| LLM07 después | `MITIGATION_LLM01=false`, `MITIGATION_LLM07=true` | `python attacks/atacar.py llm07 --etiqueta despues` |
| LLM10 antes | `MITIGATION_LLM10=false` | `python attacks/atacar.py llm10 --etiqueta antes` |
| LLM10 después | `MITIGATION_LLM10=true`, servidor recién iniciado | `python attacks/atacar.py llm10 --etiqueta despues` |
| LLM02 antes | `MITIGATION_LLM02=false`, `MOCK_FALLA=auth` | `python attacks/atacar.py llm02 --etiqueta antes` |
| LLM02 después | `MITIGATION_LLM02=true`, `MOCK_FALLA=auth` | `python attacks/atacar.py llm02 --etiqueta despues` |
| Logs antes | `MITIGATION_SAFE_LOGGING=false` | Correr cualquier ataque y abrir `logs\gateway.log` |
| Logs después | `MITIGATION_SAFE_LOGGING=true` | Igual; buscar el prompt y las keys con `Select-String` |

Notas:

- En LLM07 se apaga LLM01 a propósito, para que el ataque llegue al modelo y se pruebe solo la capa de salida. Con ambas activas, LLM01 lo detiene antes (defensa en profundidad).
- LLM10 se corre con el servidor recién iniciado, porque el límite cuenta las solicitudes de los ataques anteriores.
- Con `PROVIDER=gemini`, la demo de LLM02 se hace con una **key falsa** en `GEMINI_API_KEY`. Nunca muestres tu key real en pantalla.

### Verificar que no hay datos sensibles en logs ni en git

```powershell
Select-String -Path logs\gateway.log -Pattern "45879632", $env:GATEWAY_KEY_A, "ESC-4471", "CNRY-"
gitleaks git . --verbose
```

Ambos comandos deben terminar sin coincidencias.

## Referencia: gateway del curso

`attacks/atacar_gateway_curso.py` ejecuta ataques equivalentes contra `session_1b/backend/main.py` del repositorio del curso, que no tiene controles de seguridad. Requiere Ollama con `llama3.2`.

## Créditos

- `app/providers/gemini.py` está basado en `llamar_google()` de `session_5/backend/proveedores.py` del repositorio [Repo-Fundamentos-Arquitectura-LLM](https://github.com/arojaspa76/Repo-Fundamentos-Arquitectura-LLM) (prof. Andrés Rojas), con los cambios documentados en el propio archivo.
- Marco de referencia: OWASP Top 10 for LLM Applications 2025.
