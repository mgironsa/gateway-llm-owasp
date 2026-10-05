# Manual de usuario

Gateway LLM con seguridad de nivel producción · Proyecto final, opción 4 · Fundamentos de Arquitectura LLM (BSG Institute)

Este manual explica cómo usar el gateway una vez instalado. Para instalarlo, consulta el [Manual de instalación](MANUAL_INSTALACION.md).

## Contenido

1. [Qué es el gateway](#1-qué-es-el-gateway)
2. [Perfiles de usuario](#2-perfiles-de-usuario)
3. [Para aplicaciones cliente](#3-para-aplicaciones-cliente)
4. [Para el operador](#4-para-el-operador)
5. [Para demostraciones y evaluación](#5-para-demostraciones-y-evaluación)
6. [Preguntas frecuentes](#6-preguntas-frecuentes)

---

## 1. Qué es el gateway

El gateway es la **puerta de entrada única** entre las aplicaciones de una organización y el proveedor de modelos de lenguaje (Google Gemini). Ninguna aplicación habla directamente con el proveedor: todas envían sus consultas al gateway, que aplica los controles de seguridad, llama al modelo y devuelve la respuesta.

```
Aplicación cliente ──► Gateway (controles de seguridad) ──► Proveedor LLM
                   ◄──                                  ◄──
```

En este proyecto, el gateway atiende a un asistente de mesa de ayuda de TI de una empresa ficticia, **Andes Industrial**, que responde consultas sobre contraseñas, VPN, correo, impresoras y accesos.

### Controles que aplica

Cada solicitud pasa por estos controles, en este orden:

| # | Control | Qué hace | Categoría OWASP |
| --- | --- | --- | --- |
| 1 | Tamaño del cuerpo | Rechaza solicitudes de más de 16 KB | LLM10 |
| 2 | Autenticación | Exige una API key de cliente válida en el header `X-API-Key` | — |
| 3 | Rate limit | Limita las solicitudes por cliente (10 por minuto por defecto) | LLM10 |
| 4 | Tamaño del mensaje | Rechaza mensajes de más de 2000 caracteres | LLM10 |
| 5 | Filtro de inyección | Rechaza intentos de cambiar las instrucciones del asistente | LLM01 |
| 6 | Llamada al modelo | Con un techo de tokens por respuesta | LLM10 |
| 7 | Filtro de salida | Bloquea respuestas que revelen la configuración interna | LLM07 |
| 8 | Registro de auditoría | Guarda metadatos de la solicitud, nunca su contenido | LLM02 |

Si cualquier control rechaza la solicitud, los siguientes no se ejecutan y el modelo no se consulta.

## 2. Perfiles de usuario

| Perfil | Quién es | Secciones de este manual |
| --- | --- | --- |
| **Aplicación cliente** | El desarrollador de una aplicación que consume el gateway | [3](#3-para-aplicaciones-cliente) |
| **Operador** | Quien administra el gateway: clientes, keys, límites, logs | [4](#4-para-el-operador) |
| **Evaluador** | Quien reproduce las demostraciones de seguridad | [5](#5-para-demostraciones-y-evaluación) |

---

## 3. Para aplicaciones cliente

### 3.1. Requisitos

- La URL del gateway. En instalación local: `http://localhost:8000`.
- Una **API key de cliente**, entregada por el operador. Es personal de cada aplicación: no la compartas ni la incluyas en el código fuente.

### 3.2. Endpoints

| Método | Ruta | Autenticación | Para qué sirve |
| --- | --- | --- | --- |
| `POST` | `/v1/chat` | Sí | **Enviar una consulta al asistente.** Es el único endpoint que usa el modelo |
| `GET` | `/v1/estado` | Sí | Ver qué controles están activos y qué proveedor se usa |
| `GET` | `/health` | No | Comprobar que el gateway está en funcionamiento |
| `GET` | `/docs` | No | Documentación interactiva de la API (Swagger) |

### 3.3. Enviar una consulta

**Solicitud:**

```http
POST /v1/chat
Content-Type: application/json
X-API-Key: <tu key de cliente>

{"mensaje": "No puedo conectarme a la VPN, ¿qué reviso?"}
```

| Campo | Tipo | Obligatorio | Restricciones |
| --- | --- | --- | --- |
| `mensaje` | texto | Sí | Al menos 1 carácter; máximo 2000 (configurable) |

**Respuesta exitosa (200):**

```json
{
  "respuesta": "Para solucionar tu problema con la VPN, revisa lo siguiente: ...",
  "request_id": "f5ef5c2e25fc",
  "modelo": "gemini-3.5-flash-lite",
  "tokens": {"entrada": 127, "salida": 54}
}
```

| Campo | Qué contiene |
| --- | --- |
| `respuesta` | El texto del asistente |
| `request_id` | Identificador único de la solicitud. Guárdalo: es lo que el operador necesita para investigar un problema |
| `modelo` | El modelo que respondió (`mock-vulnerable` si es el proveedor simulado) |
| `tokens` | Consumo de la solicitud: tokens de entrada y de salida |

### 3.4. Ejemplos

**PowerShell:**

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8000/v1/chat `
  -Headers @{"X-API-Key" = $env:GATEWAY_KEY_A} `
  -ContentType "application/json" `
  -Body '{"mensaje":"No puedo conectarme a la VPN, que reviso?"}' | ConvertTo-Json
```

En Windows PowerShell 5.1, escribe el mensaje sin tildes ni ñ, o envíalo como bytes UTF-8 (ver [preguntas frecuentes](#6-preguntas-frecuentes)).

**curl:**

```bash
curl -s -X POST http://localhost:8000/v1/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $GATEWAY_KEY_A" \
  -d '{"mensaje": "No puedo conectarme a la VPN, ¿qué reviso?"}'
```

**Python:**

```python
import os
import httpx

respuesta = httpx.post(
    "http://localhost:8000/v1/chat",
    headers={"X-API-Key": os.environ["GATEWAY_KEY_A"]},
    json={"mensaje": "No puedo conectarme a la VPN, ¿qué reviso?"},
    timeout=60,
)
datos = respuesta.json()
print(respuesta.status_code, datos.get("respuesta") or datos.get("error"))
```

### 3.5. Códigos de respuesta

Todas las respuestas de error tienen la forma `{"error": "<mensaje>", "request_id": "<id>"}`. Los mensajes son genéricos a propósito: el gateway nunca revela detalles internos.

| Código | Significado | Qué hacer |
| --- | --- | --- |
| **200** | Consulta respondida | — |
| **400** | La consulta fue rechazada por la política de seguridad (posible inyección) o el cuerpo no es JSON válido | Reformula la consulta. Si crees que es un error, entrega el `request_id` al operador |
| **401** | API key ausente o inválida | Verifica el header `X-API-Key`. Si la key fue rotada, pide la nueva al operador |
| **413** | El mensaje o la solicitud son demasiado grandes | Acorta el mensaje (máximo 2000 caracteres) |
| **422** | Formato de solicitud inválido (por ejemplo, falta `mensaje` o no es texto) | Revisa el campo indicado en `campos` |
| **429** | Superaste el límite de solicitudes de tu cliente | Espera y reintenta. Por defecto el límite se renueva cada minuto |
| **502** | El proveedor devolvió una respuesta inválida | Reintenta más tarde |
| **503** | El servicio de IA no está disponible temporalmente | Reintenta más tarde con espera progresiva |
| **504** | El servicio de IA no respondió a tiempo | Reintenta más tarde |
| **500** | Error interno del gateway | Entrega el `request_id` al operador |

**Reintentos recomendados:** ante 429, 502, 503 o 504, reintenta con espera progresiva (por ejemplo, 2, 4 y 8 segundos) y un máximo de tres intentos. No reintentes los 400, 401, 413 ni 422: repetir la misma solicitud dará el mismo resultado.

### 3.6. Respuesta neutra del asistente

Si la respuesta del modelo contiene información de la configuración interna del asistente, el gateway la reemplaza por:

> "No puedo compartir información sobre mi configuración interna. ¿En qué tema de soporte de TI te ayudo?"

El código sigue siendo 200. Si recibes este mensaje ante una consulta legítima, reformúlala y avisa al operador con el `request_id`: puede ser un falso positivo del filtro.

### 3.7. Buenas prácticas

- **Guarda la API key en una variable de entorno o en un gestor de secretos**, nunca en el código fuente ni en un repositorio.
- **No envíes datos personales ni confidenciales reales** en las consultas: el proveedor del modelo es un tercero.
- **Registra el `request_id`** de cada solicitud en tu aplicación, para poder rastrear problemas.
- **Respeta el rate limit:** agrupa consultas cuando sea posible y aplica espera progresiva ante un 429.

---

## 4. Para el operador

### 4.1. Ver el estado del gateway

```powershell
curl.exe -s http://localhost:8000/v1/estado -H "X-API-Key: $env:GATEWAY_KEY_A"
```

Muestra el proveedor, el modelo, los cinco controles y el rate limit **tal como se cargaron al arrancar**. Si no coinciden con el `.env`, falta reiniciar el gateway.

### 4.2. Dar de alta o de baja un cliente

1. Genera una key: `python tools/generar_api_key.py`.
2. Edita `CLIENT_API_KEYS` en `.env`. El formato es `alias:key`, separados por comas:
   ```
   CLIENT_API_KEYS=cliente-a:gw_...,cliente-b:gw_...,app-intranet:gw_...
   ```
   Para dar de baja un cliente, borra su par `alias:key`.
3. Reinicia el gateway.
4. Entrega la key al cliente por un canal seguro (gestor de contraseñas compartido o mensaje cifrado), nunca por correo en texto plano ni en un chat.

El alias es lo que aparece en los logs como `cliente_id`; la key nunca se registra.

### 4.3. Rotar credenciales

Rota una credencial **de inmediato** si apareció en una captura, un video, un chat, un log o un commit, aunque después la hayas borrado. Rótalas también de forma periódica y después de cada demostración.

| Credencial | Cómo rotarla |
| --- | --- |
| Key de cliente | Genera una nueva, reemplázala en `CLIENT_API_KEYS`, reinicia y entrégala al cliente. La anterior deja de funcionar al instante |
| Key de Gemini | En Google AI Studio, borra la key y crea otra. Actualiza `GEMINI_API_KEY` y reinicia |
| `LOG_HMAC_KEY` | Genera una nueva y reinicia. Las huellas de prompts anteriores dejarán de ser comparables con las nuevas |

### 4.4. Ajustar los límites

| Variable | Por defecto | Efecto |
| --- | --- | --- |
| `RATE_LIMIT` | `10/minute` | Solicitudes por cliente. Acepta formatos como `100/hour` o `5/second` |
| `MAX_PROMPT_CHARS` | `2000` | Longitud máxima del mensaje |
| `MAX_OUTPUT_TOKENS` | `300` | Techo de tokens por respuesta. Súbelo si las respuestas salen cortadas |
| `MAX_BODY_BYTES` | `16384` | Tamaño máximo de la solicitud |
| `UPSTREAM_TIMEOUT_S` | `20` | Segundos de espera al proveedor antes de responder 504 |

Reinicia el gateway después de cualquier cambio. El contador del rate limit vive en memoria: también se reinicia.

### 4.5. Cambiar de proveedor o de modelo

| Para | Configuración |
| --- | --- |
| Usar Gemini | `PROVIDER=gemini`, `GEMINI_API_KEY=<key>`, `GEMINI_MODEL=gemini-3.5-flash-lite` |
| Trabajar sin red, sin costo o en pruebas | `PROVIDER=mock` |

Si Gemini falla, ejecuta `python tools/diagnosticar_gemini.py` para ver la causa (detallado en el [Manual de instalación](MANUAL_INSTALACION.md#9-conectar-google-gemini-opcional)).

### 4.6. Leer los logs

El gateway escribe una línea JSON por solicitud en `logs/gateway.log`.

```powershell
# Última solicitud, en formato legible
Get-Content logs\gateway.log -Encoding UTF8 -Tail 1 | ConvertFrom-Json | Format-List

# Buscar una solicitud por su request_id
Select-String -Path logs\gateway.log -Pattern "f5ef5c2e25fc"
```

| Campo | Qué indica |
| --- | --- |
| `timestamp` | Fecha y hora |
| `request_id` | Identificador de la solicitud (el mismo que recibió el cliente) |
| `endpoint`, `metodo` | Ruta y método HTTP |
| `status_code` | Código de respuesta enviado al cliente |
| `latencia_ms` | Tiempo total de la solicitud |
| `cliente_id` | Alias del cliente, nunca su key |
| `mitigacion` | Control que actuó: `LLM10`, `LLM01`, `LLM07` o `LLM02` |
| `motivo` | Detalle del control, por ejemplo `ignorar_instrucciones_es`, `canary_en_respuesta` o `prompt_excede_limite` |
| `proveedor`, `modelo` | Quién respondió |
| `tokens_entrada`, `tokens_salida` | Consumo de la solicitud |
| `longitud_prompt`, `prompt_hmac` | Tamaño y huella del mensaje, **sin su contenido** |
| `tipo_error` | Causa de una falla del proveedor: `timeout`, `auth`, `cuota`, `no_disponible` o `malformada` |

**El log nunca contiene** el texto de los mensajes o las respuestas, las API keys, el system prompt ni los mensajes de error del proveedor. Con el mismo `prompt_hmac` puedes saber que dos solicitudes enviaron exactamente el mismo texto, sin conocerlo.

### 4.7. Investigar un incidente

Cuando un cliente reporta un problema con un `request_id`:

1. Busca la línea: `Select-String -Path logs\gateway.log -Pattern "<request_id>"`.
2. Revisa `status_code`, `mitigacion`, `motivo` y `tipo_error`.

| Lo que ves | Interpretación |
| --- | --- |
| `mitigacion: LLM01` | El filtro de inyección rechazó la consulta. `motivo` indica el patrón. Si la consulta era legítima, es un falso positivo |
| `mitigacion: LLM07` | Se bloqueó la respuesta por posible filtración. `motivo: canary_en_respuesta` indica que el modelo reprodujo la marca interna |
| `mitigacion: LLM10` | Rate limit o tamaño excedido |
| `tipo_error` presente | Falla del proveedor. Para el detalle, usa `tools/diagnosticar_gemini.py` |
| Muchas solicitudes `LLM01` del mismo `cliente_id` | Posible abuso o una aplicación comprometida: considera rotar su key |

### 4.8. Ejecutar las pruebas automáticas

```powershell
python -m pytest -v
```

Ejecuta las 29 pruebas antes de cualquier despliegue y después de cualquier cambio en la configuración de seguridad.

---

## 5. Para demostraciones y evaluación

Cada control tiene un **interruptor** para mostrar el comportamiento sin protección (línea base) y con protección, usando el mismo código.

> ⚠️ **Los interruptores en `false` existen solo para demostraciones.** En particular, **nunca uses `MITIGATION_LLM02=false` con una key real de Gemini**: ese modo reproduce el error de diseño de enviar la key en la URL y devolverla en los mensajes de error. Usa siempre una key falsa, por ejemplo `AIzaSyFAKE-0000-demo-no-es-real-0000`.

### 5.1. Interruptores

| Variable | En `false` (línea base) | En `true` (protegido) |
| --- | --- | --- |
| `MITIGATION_LLM10` | Sin límite de solicitudes ni de tamaño | 429 al superar el límite; 413 por tamaño |
| `MITIGATION_LLM01` | Las inyecciones llegan al modelo | 400 antes de llegar al modelo |
| `MITIGATION_LLM07` | Las respuestas salen sin revisión | Las filtraciones se reemplazan por un mensaje neutro |
| `MITIGATION_LLM02` | Errores con detalle interno y key en la URL | Errores genéricos con `request_id` |
| `MITIGATION_SAFE_LOGGING` | El log guarda prompts, respuestas y headers | El log guarda solo metadatos |

### 5.2. Scripts de ataque

Con el gateway corriendo, en otra terminal:

```powershell
$env:GATEWAY_KEY_A = "<key de cliente-a>"
$env:GATEWAY_KEY_B = "<key de cliente-b>"

python attacks/atacar.py llm01 --etiqueta antes     # o --etiqueta despues
python attacks/atacar.py llm07 --etiqueta antes
python attacks/atacar.py llm10 --etiqueta antes
python attacks/atacar.py llm02 --etiqueta antes
python attacks/atacar.py todos --etiqueta antes      # llm01 + llm07
```

La salida se muestra en pantalla y se guarda en `docs/evidencia/<etiqueta>/<categoria>.txt`. Para separar corridas, define una subcarpeta: `$env:EVIDENCIA_SUB = "Gemini"` guarda en `docs/evidencia/<etiqueta>/Gemini/`.

| Ataque | Requisito |
| --- | --- |
| `llm10` | Reiniciar el gateway antes, para que el contador empiece en cero |
| `llm02` | Proveedor en falla: `MOCK_FALLA=auth` con `mock`, o una key **falsa** con `gemini` |
| `llm07` | Para probar solo la capa de salida, apagar LLM01 |

### 5.3. Simular fallas del proveedor

Con `PROVIDER=mock`, la variable `MOCK_FALLA` simula fallas para probar la degradación controlada:

| Valor | Simula | Respuesta con `MITIGATION_LLM02=true` |
| --- | --- | --- |
| `ninguna` | Funcionamiento normal | 200 |
| `timeout` | El proveedor no responde a tiempo | 504 |
| `auth` | El proveedor rechaza la credencial | 503 |
| `malformada` | Respuesta que el gateway no puede interpretar | 502 |

Vuelve siempre a `MOCK_FALLA=ninguna` al terminar.

### 5.4. Recomendaciones para una demostración limpia

- Verifica con `/v1/estado` **antes de cada prueba** que los interruptores son los esperados.
- Para revisar el log desde cero, **detén el gateway antes de borrarlo** (en Windows, el archivo queda bloqueado mientras el gateway corre) y confirma con `Test-Path logs\gateway.log`.
- No muestres el `.env` en pantalla, o deja las credenciales fuera de la vista.
- **Rota todas las credenciales al terminar** la demostración ([4.3](#43-rotar-credenciales)).

---

## 6. Preguntas frecuentes

**¿Por qué recibo 400 si mi consulta es legítima?**
El filtro de inyección busca patrones como "ignora tus instrucciones" o "system prompt". Si tu consulta los contiene por otro motivo, reformúlala. Si el problema se repite, entrega el `request_id` al operador.

**¿Por qué recibo 400 "There was an error parsing the body"?**
El cuerpo no llegó como JSON válido. En Windows PowerShell 5.1 ocurre con tildes y ñ. Envía el cuerpo como bytes UTF-8:

```powershell
$cuerpo = '{"mensaje":"¿Cómo configuro la VPN?"}'
Invoke-RestMethod -Method Post -Uri http://localhost:8000/v1/chat -Headers @{"X-API-Key"=$env:GATEWAY_KEY_A} -ContentType "application/json; charset=utf-8" -Body ([Text.Encoding]::UTF8.GetBytes($cuerpo))
```

**¿Por qué el mensaje de error no dice qué falló?**
Por diseño. Los detalles internos (URLs, librerías, mensajes del proveedor) pueden revelar credenciales o información útil para un atacante. El operador ve la causa en el log mediante el `request_id`.

**¿El gateway guarda mis consultas?**
No. El log registra la longitud del mensaje y una huella criptográfica (HMAC) que no permite recuperar el texto.

**¿Cómo sé si la respuesta viene de Gemini o del simulador?**
Por el campo `modelo`: `mock-vulnerable` es el simulador. El simulador además empieza sus respuestas normales con `[MOCK]`.

**¿Qué pasa si se agota la cuota de Gemini?**
Recibirás 503. El operador verá `tipo_error: cuota` en el log. En la capa gratuita, la cuota se recupera en un minuto o al día siguiente, según el límite alcanzado.
