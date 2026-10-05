# Gateway LLM con Seguridad de Nivel Producción

Proyecto final · Opción 4 · Fundamentos de Arquitectura LLM (BSG Institute)

Gateway FastAPI que actúa como **único punto de entrada** (`POST /v1/chat`) entre las aplicaciones y el proveedor LLM (Google Gemini). Implementa y demuestra cuatro categorías del **OWASP Top 10 for LLM Applications (2025)**: LLM10, LLM01, LLM07 y LLM02. Cada mitigación se enciende o apaga con una variable de entorno, para mostrar el comportamiento antes y después con el mismo código.

## Documentación

| Documento | Contenido |
| --- | --- |
| [Manual de instalación](docs/MANUAL_INSTALACION.md) | Requisitos, instalación desde cero en Windows, configuración, conexión con Gemini y solución de problemas |
| [Manual de usuario](docs/MANUAL_USUARIO.md) | Uso de la API por aplicaciones cliente, tareas del operador (clientes, keys, límites, logs) y guía de demostración |
| [Mapeo OWASP](docs/MAPEO_OWASP.md) | **Entregable central:** cada categoría OWASP con su riesgo, ataque, mitigación, evidencia antes/después y límites |
| [Evidencias de ejecuciones](docs/Evidencias%20de%20ejecuciones.docx) | Capturas de pantalla de las pruebas |

## Inicio rápido

Requisitos: Python 3.12 o superior, Git y gitleaks. El detalle de cada paso está en el [Manual de instalación](docs/MANUAL_INSTALACION.md).

```powershell
git clone https://github.com/mgironsa/gateway-llm-owasp.git
cd gateway-llm-owasp
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pre-commit install
copy .env.example .env          # completar CLIENT_API_KEYS y LOG_HMAC_KEY
python -m pytest -v             # 29 passed
uvicorn app.main:app --port 8000
```

Consulta de prueba, desde otra terminal:

```powershell
$env:GATEWAY_KEY_A = "<key de cliente-a>"
Invoke-RestMethod -Method Post -Uri http://localhost:8000/v1/chat -Headers @{"X-API-Key"=$env:GATEWAY_KEY_A} -ContentType "application/json" -Body '{"mensaje":"No puedo conectarme a la VPN, que reviso?"}'
```

## Controles implementados

| # | Control | Categoría | Módulo |
| --- | --- | --- | --- |
| 1 | Límite de tamaño del cuerpo | LLM10 | `app/main.py` |
| 2 | Autenticación por `X-API-Key` | — | `app/auth.py` |
| 3 | Rate limit por API key de cliente | LLM10 | `app/security/rate_limit.py` |
| 4 | Límite de tamaño del mensaje | LLM10 | `app/main.py` |
| 5 | Filtro de inyección y delimitación | LLM01 | `app/security/input_guard.py` |
| 6 | Llamada al proveedor con techo de tokens y key en header | LLM10, LLM02 | `app/providers/gemini.py` |
| 7 | Canary y filtro de filtración del system prompt | LLM07 | `app/security/output_guard.py` |
| 8 | Errores genéricos y logging con lista blanca | LLM02 | `app/errors.py`, `app/logging_seguro.py` |

Además: credenciales como `SecretStr`, gitleaks en cada commit (pre-commit) y CORS restringido a orígenes explícitos.

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
attacks/
  atacar.py             ataques reproducibles que generan la evidencia
  atacar_gateway_curso.py  los mismos ataques contra el gateway del curso
tests/                  29 pruebas pytest, antes y después de cada mitigación
tools/                  utilidades locales del operador (generar keys, diagnosticar Gemini);
                        no forman parte del gateway ni se exponen por red
docs/
  MANUAL_INSTALACION.md
  MANUAL_USUARIO.md
  MAPEO_OWASP.md        entregable central
  Evidencias de ejecuciones.docx
  evidencia/
    antes/  despues/    salidas de los ataques, por entorno:
      Mock-QA/          proveedor simulado
      Gemini/           Gemini real
      Video/            corridas grabadas en el video
```

## Reproducir la evidencia

El procedimiento completo, con la configuración de cada prueba, está en el [Manual de usuario, sección 5](docs/MANUAL_USUARIO.md#5-para-demostraciones-y-evaluación). Resumen:

| Categoría | Configuración en `.env` | Comando |
| --- | --- | --- |
| LLM01 | `MITIGATION_LLM01=false` / `true` | `python attacks/atacar.py llm01 --etiqueta antes` / `despues` |
| LLM07 | `MITIGATION_LLM07=false` / `true` (con `MITIGATION_LLM01=false` para probar solo la salida) | `python attacks/atacar.py llm07 --etiqueta antes` / `despues` |
| LLM10 | `MITIGATION_LLM10=false` / `true`, con el gateway recién reiniciado | `python attacks/atacar.py llm10 --etiqueta antes` / `despues` |
| LLM02 | `MITIGATION_LLM02=false` / `true`, con `MOCK_FALLA=auth` | `python attacks/atacar.py llm02 --etiqueta antes` / `despues` |

> ⚠️ **Nunca ejecutes `MITIGATION_LLM02=false` con una key real de Gemini.** Ese modo expone la key en los mensajes de error. Usa una key falsa, como `AIzaSyFAKE-0000-demo-no-es-real-0000`.

El gateway lee `.env` solo al arrancar: reinícialo después de cada cambio y verifica con `GET /v1/estado`.

## Fuentes

- `app/providers/gemini.py` está basado en `llamar_google()` de `session_5/backend/proveedores.py` del repositorio [Repo-Fundamentos-Arquitectura-LLM](https://github.com/arojaspa76/Repo-Fundamentos-Arquitectura-LLM) (prof. Andrés Rojas), con los cambios de seguridad documentados en el propio archivo.
- Marco de referencia: OWASP Top 10 for LLM Applications 2025.
- Parte del código y de la documentación se elaboró con asistencia de IA (Claude, de Anthropic), revisada y validada por Miguel Giron.
