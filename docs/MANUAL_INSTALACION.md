# Manual de instalación

Gateway LLM con seguridad de nivel producción · Proyecto final, opción 4 · Fundamentos de Arquitectura LLM (BSG Institute)

Este manual describe cómo instalar, configurar y verificar el gateway desde un equipo sin nada instalado. Al terminar tendrás el gateway funcionando con el proveedor simulado (`mock`) y, opcionalmente, con Google Gemini.

Para usar el gateway una vez instalado, consulta el [Manual de usuario](MANUAL_USUARIO.md).

## Contenido

1. [Requisitos](#1-requisitos)
2. [Instalar el software base](#2-instalar-el-software-base)
3. [Obtener el código](#3-obtener-el-código)
4. [Crear el entorno de Python](#4-crear-el-entorno-de-python)
5. [Configurar el archivo `.env`](#5-configurar-el-archivo-env)
6. [Activar la protección de secretos en git](#6-activar-la-protección-de-secretos-en-git)
7. [Verificar la instalación](#7-verificar-la-instalación)
8. [Arrancar el gateway](#8-arrancar-el-gateway)
9. [Conectar Google Gemini (opcional)](#9-conectar-google-gemini-opcional)
10. [Solución de problemas](#10-solución-de-problemas)
11. [Desinstalar](#11-desinstalar)

---

## 1. Requisitos

| Elemento | Requisito | Probado con |
| --- | --- | --- |
| Sistema operativo | Windows 10 u 11 (también funciona en Linux y macOS) | Windows 11 |
| Python | 3.12 o superior | 3.12 y 3.14.8 |
| Git | Cualquier versión reciente | Git para Windows |
| gitleaks | 8.x | 8.30.1 |
| Editor | Opcional; se recomienda Visual Studio Code | VS Code |
| Hardware | Cualquier equipo actual; el modelo corre en los servidores del proveedor | Laptop estándar |
| Red | Internet solo para instalar dependencias y para usar Gemini. El proveedor `mock` funciona sin conexión | — |
| Cuenta | Cuenta de Google, solo si usarás Gemini | Capa gratuita de Google AI Studio |

> **Ubicación recomendada:** una carpeta corta, sin espacios ni tildes y **fuera de OneDrive**, por ejemplo `C:\dev`. Si el proyecto queda en una carpeta sincronizada, el archivo `.env` con las credenciales se subiría a la nube.

## 2. Instalar el software base

Abre **PowerShell** (no hace falta que sea como administrador) y ejecuta:

```powershell
winget install -e --id Python.Python.3.12
winget install -e --id Git.Git
winget install -e --id Gitleaks.Gitleaks
winget install -e --id Microsoft.VisualStudioCode
```

**Cierra y vuelve a abrir PowerShell** para que se actualice el `PATH`, y verifica:

```powershell
py --version
git --version
gitleaks version
code --version
```

Si ya tienes una versión más nueva de Python (por ejemplo, 3.14), puedes usarla: el proyecto se probó con 3.12 y 3.14.

Configura tu identidad en Git (solo la primera vez):

```powershell
git config --global user.name "Tu Nombre"
git config --global user.email "tu@correo.com"
```

**Linux o macOS:** instala Python 3.12+, Git y gitleaks con el gestor de paquetes del sistema (`apt`, `brew`, etc.). Los comandos de los pasos siguientes cambian solo en la activación del entorno (`source .venv/bin/activate`) y en el copiado de archivos (`cp`).

## 3. Obtener el código

```powershell
mkdir C:\dev
cd C:\dev
git clone https://github.com/mgironsa/gateway-llm-owasp.git
cd gateway-llm-owasp
```

## 4. Crear el entorno de Python

**4.1. Permitir scripts locales en PowerShell** (una sola vez por usuario). Windows bloquea por defecto el script que activa el entorno virtual:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Responde `S` para confirmar. `RemoteSigned` permite ejecutar scripts creados en tu equipo y sigue exigiendo firma a los descargados de internet. Si prefieres no cambiarlo de forma permanente, usa `Set-ExecutionPolicy -Scope Process Bypass`, que solo afecta a la ventana actual.

**4.2. Crear y activar el entorno virtual:**

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
```

El prompt cambia a `(.venv) PS C:\dev\gateway-llm-owasp>`. Cada vez que abras una terminal nueva para trabajar con el proyecto, repite la activación.

**4.3. Instalar las dependencias:**

```powershell
pip install -r requirements.txt
```

Se instalan FastAPI, Uvicorn, Pydantic, pydantic-settings, httpx, slowapi, python-json-logger, pytest y pre-commit.

## 5. Configurar el archivo `.env`

El gateway lee toda su configuración del archivo `.env`, que **nunca se sube a git** (está en `.gitignore`).

**5.1. Crear el archivo a partir de la plantilla:**

```powershell
copy .env.example .env
```

**5.2. Generar las credenciales.** Ejecuta tres veces:

```powershell
python tools/generar_api_key.py
```

Cada ejecución imprime un valor aleatorio como `gw_Xk3...`. Abre el archivo con `code .env` y completa:

```
CLIENT_API_KEYS=cliente-a:<valor 1>,cliente-b:<valor 2>
LOG_HMAC_KEY=<valor 3>
```

Guarda los valores 1 y 2 en un gestor de contraseñas: son las credenciales que usarán las aplicaciones cliente.

**5.3. Revisar el resto de la configuración.** Para la instalación inicial deja `PROVIDER=mock` y las cinco `MITIGATION_...=true`.

| Variable | Valor recomendado | Para qué sirve |
| --- | --- | --- |
| `PROVIDER` | `mock` | Proveedor del modelo: `mock` (simulado, sin red) o `gemini` |
| `GEMINI_API_KEY` | vacío | Key de Google AI Studio; solo con `PROVIDER=gemini` |
| `GEMINI_MODEL` | `gemini-3.5-flash-lite` | Modelo de Gemini. Ver [paso 9](#9-conectar-google-gemini-opcional) |
| `CLIENT_API_KEYS` | `alias:key,alias:key` | Clientes autorizados a usar el gateway |
| `LOG_HMAC_KEY` | valor aleatorio | Sal secreta para la huella de los prompts en los logs |
| `MITIGATION_LLM10` | `true` | Rate limit por cliente y límites de tamaño |
| `MITIGATION_LLM01` | `true` | Filtro de prompt injection |
| `MITIGATION_LLM07` | `true` | Filtro de filtración del system prompt |
| `MITIGATION_LLM02` | `true` | Errores genéricos y key del proveedor en el header |
| `MITIGATION_SAFE_LOGGING` | `true` | Logs sin datos sensibles |
| `RATE_LIMIT` | `10/minute` | Solicitudes permitidas por cliente |
| `MAX_PROMPT_CHARS` | `2000` | Longitud máxima del mensaje |
| `MAX_OUTPUT_TOKENS` | `300` | Techo de tokens por respuesta del modelo |
| `MOCK_FALLA` | `ninguna` | Simula fallas del proveedor `mock`: `ninguna`, `timeout`, `auth` o `malformada` |

Variables opcionales que no están en la plantilla y usan su valor por defecto: `MAX_BODY_BYTES` (16384), `UPSTREAM_TIMEOUT_S` (20), `LOG_PATH` (`logs/gateway.log`) y `CORS_ORIGINS` (`http://localhost:5173`).

> ⚠️ **Los valores `true`/`false` deben escribirse exactamente así.** Un valor mal escrito (por ejemplo, `falase`) impide que el gateway arranque. Es intencional: una protección mal configurada no debe quedar en un estado indefinido.
>
> ⚠️ **Cada variable debe aparecer una sola vez.** Si una variable está repetida, gana la última línea.

## 6. Activar la protección de secretos en git

El proyecto incluye un hook de pre-commit que ejecuta gitleaks antes de cada commit y bloquea cualquier credencial.

```powershell
pre-commit install
```

**Prueba el hook** con una key falsa con formato de Google:

```powershell
Set-Content prueba_fuga.py 'GEMINI_API_KEY = "AIzaSyD4kX9qLm2Rt7vWb3Np8Hc5Jf1Gz6Ys0Ue"'
git add prueba_fuga.py
git commit -m "prueba"
```

Debe aparecer `gitleaks (detectar secretos)....Failed` con la regla `gcp-api-key`. Limpia la prueba:

```powershell
git reset prueba_fuga.py
Remove-Item prueba_fuga.py
```

> **Límite de gitleaks:** solo analiza texto. **No detecta credenciales dentro de imágenes ni de documentos de Word.** Revisa a mano cualquier captura de pantalla antes de subirla.

## 7. Verificar la instalación

```powershell
python -m pytest -v
```

Resultado esperado: **29 passed**. Las pruebas usan su propia configuración y el proveedor `mock`, así que no dependen de tu `.env` ni de internet. El aviso `StarletteDeprecationWarning` es informativo y no afecta.

## 8. Arrancar el gateway

**Terminal 1** (queda ocupada mientras el gateway corre):

```powershell
cd C:\dev\gateway-llm-owasp
.venv\Scripts\Activate.ps1
uvicorn app.main:app --port 8000
```

Debe mostrar `Uvicorn running on http://127.0.0.1:8000`.

**Terminal 2** (para hacer consultas):

```powershell
cd C:\dev\gateway-llm-owasp
.venv\Scripts\Activate.ps1
$env:GATEWAY_KEY_A = "<valor 1 de CLIENT_API_KEYS>"

curl.exe -s http://localhost:8000/health
curl.exe -s http://localhost:8000/v1/estado -H "X-API-Key: $env:GATEWAY_KEY_A"
```

- `/health` debe responder `{"estado":"ok"}`.
- `/v1/estado` debe mostrar `"proveedor":"mock"` y las cinco mitigaciones en `true`.

Prueba una consulta:

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8000/v1/chat -Headers @{"X-API-Key"=$env:GATEWAY_KEY_A} -ContentType "application/json" -Body '{"mensaje":"No puedo conectarme a la VPN, que reviso?"}' | ConvertTo-Json
```

Con el proveedor `mock`, la respuesta empieza con `[MOCK] Respuesta de soporte de TI para: ...`.

> **El gateway lee el `.env` solo al arrancar.** Después de cualquier cambio, reinícialo: en la terminal 1, Ctrl+C, flecha arriba y Enter.

## 9. Conectar Google Gemini (opcional)

**9.1. Obtener la key.** Entra a [aistudio.google.com](https://aistudio.google.com) con una cuenta personal de Google, acepta los términos, ve a **Get API key** y crea una key. Guárdala en tu gestor de contraseñas.

> En la capa gratuita, Google puede usar el contenido de las solicitudes para mejorar sus productos. Usa solo datos ficticios.

**9.2. Configurar el `.env`:**

```
PROVIDER=gemini
GEMINI_API_KEY=<tu key>
GEMINI_MODEL=gemini-3.5-flash-lite
```

Reinicia el gateway y verifica con `/v1/estado` que diga `"proveedor":"gemini"`.

**9.3. Diagnosticar la conexión.** Si las consultas devuelven 503 o 504, el gateway oculta el motivo al cliente, como corresponde. Para ver la causa real sin exponer la key:

```powershell
python tools/diagnosticar_gemini.py
```

- `OK -> ...`: Gemini responde; reinicia el gateway.
- `ERROR tipo: no_disponible` con un 404: el modelo fue retirado. El propio mensaje de Google sugiere el reemplazo; actualiza `GEMINI_MODEL`.
- `ERROR tipo: auth`: la key está mal copiada o fue revocada.
- `ERROR tipo: malformada`: aumenta `MAX_OUTPUT_TOKENS` (por ejemplo, a `1024`); los modelos con razonamiento pueden agotar el techo antes de responder.

Para listar los modelos disponibles para tu key:

```powershell
$k = (Select-String -Path .env -Pattern "^GEMINI_API_KEY=").Line.Split("=",2)[1]
curl.exe -s "https://generativelanguage.googleapis.com/v1beta/models?pageSize=10" -H "x-goog-api-key: $k"
```

> Un modelo puede aparecer en la lista y aun así no aceptar solicitudes de cuentas nuevas. Durante el proyecto ocurrió con `gemini-2.5-flash` y `gemini-2.5-flash-lite`.

## 10. Solución de problemas

| Síntoma | Causa | Solución |
| --- | --- | --- |
| `No runtime installed that matches 3.12` | Tienes otra versión de Python | Usa `py -m venv .venv` con la versión instalada, o instala 3.12 con `py install 3.12` |
| `No se puede cargar el archivo ...Activate.ps1` | Política de ejecución de PowerShell | [Paso 4.1](#4-crear-el-entorno-de-python) |
| `Input should be a valid boolean ... input_value='falase'` | Valor mal escrito en `.env` | Corrige a `true` o `false` exactamente |
| La configuración no cambia después de editar `.env` | El gateway no se reinició, el archivo no se guardó o la variable está duplicada | Guarda (Ctrl+S), busca duplicados con Ctrl+F y reinicia. Confirma con `/v1/estado` |
| `HTTP 401` en todas las consultas | La key de la terminal no coincide con la del `.env` | Actualiza `$env:GATEWAY_KEY_A` y reinicia el gateway |
| `HTTP 400` "There was an error parsing the body" | Windows PowerShell 5.1 no envía tildes ni ñ en UTF-8 | Escribe el mensaje sin tildes, o envía el cuerpo con `-ContentType "application/json; charset=utf-8" -Body ([Text.Encoding]::UTF8.GetBytes($cuerpo))` |
| Caracteres como `crÃ­tico` en la consola | Visualización de PowerShell 5.1 | Solo es visual; los datos son correctos. PowerShell 7 lo muestra bien |
| `HTTP 503` con Gemini | Key, modelo o cuota | [Paso 9.3](#9-conectar-google-gemini-opcional) |
| `Remove-Item logs\gateway.log` no borra el archivo | El gateway lo tiene abierto | Detén el gateway (Ctrl+C) antes de borrarlo; confirma con `Test-Path logs\gateway.log` |
| `unable to unlink ... .docx` al hacer commit | Un documento está abierto en Word | Cierra el documento y repite |
| `docx2txt.exe: command not found` en gitleaks | Git para Windows intenta convertir `.docx` a texto | Agrega `*.docx binary` en `.gitattributes` |
| Avisos `LF will be replaced by CRLF` | Conversión de saltos de línea de Git en Windows | Son informativos; no afectan |
| `git push` rechazado (`fetch first`) | El repositorio de GitHub se creó con README o licencia | En un repo recién creado: `git push -u origin main --force` |

## 11. Desinstalar

1. Detén el gateway (Ctrl+C).
2. Revoca en Google AI Studio la key de Gemini, si la creaste para este proyecto.
3. Borra la carpeta del proyecto: `Remove-Item -Recurse -Force C:\dev\gateway-llm-owasp`.
4. Opcional: desinstala las herramientas con `winget uninstall` (Python, Git, gitleaks, VS Code).
