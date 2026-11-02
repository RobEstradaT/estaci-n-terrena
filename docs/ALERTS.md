# Alertas y diagnóstico (Prototipo 8)

## Alcance

- Detección y visualización de: señal débil, pérdida de enlace, datos inválidos y errores del puerto serial.
- Umbrales configurables por variables de entorno (`ALERT_*`), con valores por omisión **provisionales**.
- Estado de las tramas del CanSat en el encabezado (distinto del indicador "ENLACE ACTIVO", que solo refleja la conexión navegador-backend).
- Panel con alertas activas, contadores de diagnóstico de la fuente serial y eventos recientes.

Fuera de este alcance (pendiente): guardar las alertas en SQLite junto a la misión, alertas sonoras o notificaciones, y alertas por variable física (p. ej. altitud, presión) más allá de las advertencias de rango ya existentes en `processor.py`.

## Arquitectura

```text
telemetry_loop  ──► processor.process ──► alert_engine.on_reading(lectura)
alerts_loop (1 s) ─► alert_engine.tick(fuente conectada, source.diagnostics())
                              │
                              ▼
                   alert_engine.snapshot()  ──► WebSocket {"type":"alerts"} ──► AlertPanel / MissionHeader
                                            └─► GET /api/alerts
```

- `backend/app/alerts.py`: motor de alertas. No conoce FastAPI, WebSocket, SQLite ni el puerto serial; recibe diccionarios y tiempo monotónico, por lo que se prueba sin hardware.
- `TelemetrySource.diagnostics()`: método opcional de las fuentes. `SerialESP32` devuelve contadores; `Simulator` devuelve `{}`.
- El mismo WebSocket (`/ws/telemetry`) transporta lecturas (sin campo `type`) y mensajes `{"type": "alerts", ...}` cada segundo. El hook `useTelemetrySocket` los separa.
- Un fallo en el motor de alertas se registra en el log y **no** interrumpe la telemetría en vivo ni el guardado.

## Alertas

| Código | Severidad | Condición | Se resuelve cuando |
|---|---|---|---|
| `WEAK_RSSI` | Aviso / Crítica | RSSI ≤ `ALERT_RSSI_WARN_DBM` (aviso) o ≤ `ALERT_RSSI_CRIT_DBM` (crítica) | RSSI supera el umbral del nivel más la histéresis |
| `LOW_SNR` | Aviso | SNR ≤ `ALERT_SNR_WARN_DB` | SNR supera el umbral más la histéresis |
| `LINK_LOST` | Crítica | Se recibió al menos una trama y pasan más de `ALERT_LINK_TIMEOUT_S` s sin una trama válida | Llega una trama válida |
| `INVALID_DATA` | Aviso | `ALERT_INVALID_CONSECUTIVE` lecturas seguidas con valores fuera de rango (`valid = false`) | Llega una lectura válida |
| `SERIAL_UNAVAILABLE` | Crítica | `source.is_connected()` es falso (puerto ausente o desconectado) | La fuente vuelve a conectarse |
| `FRAME_ERRORS` | Aviso | `ALERT_DISCARD_COUNT` o más tramas descartadas en `ALERT_DISCARD_WINDOW_S` s | Pasa una ventana completa sin descartes |

Reglas de comportamiento:

- **Histéresis** (RSSI y SNR): una alerta sube en cuanto se cruza el umbral, pero solo baja cuando el valor supera el umbral por `ALERT_HYSTERESIS_DB`. Una crítica baja primero a aviso. Evita que la alerta parpadee con el ruido de la medición.
- **Estado "en espera"**: antes de la primera trama el enlace está en `waiting` y no se genera `LINK_LOST` (es lo normal antes del lanzamiento o antes de que el CanSat encienda).
- **Pérdida de enlace**: al activarse `LINK_LOST` se resuelven `WEAK_RSSI`, `LOW_SNR` e `INVALID_DATA`, porque describían lecturas que ya no son actuales.
- **Señal débil y validez**: `processor.py` ya no marca como inválida una lectura por RSSI bajo (antes lo hacía con un umbral fijo de −110 dBm). La señal débil se evalúa solo en el motor de alertas; así no hay dos umbrales distintos para lo mismo ni una alerta doble.
- Las tramas descartadas por `parse_frame` (formato, `pass`, valores no numéricos, `nan`, `inf`) alimentan `FRAME_ERRORS`; las líneas vacías no cuentan.
- Las alertas y los eventos viven en memoria: se pierden al reiniciar el backend. Se conservan los últimos 50 eventos y se envían los 20 más recientes.

## Umbrales y justificación

| Variable | Por omisión | Estado | Justificación |
|---|---|---|---|
| `ALERT_RSSI_WARN_DBM` | −100 | PROVISIONAL | Margen antes del umbral crítico para avisar con tiempo. |
| `ALERT_RSSI_CRIT_DBM` | −110 | PROVISIONAL | Es el valor que ya usaba `processor.py` para "posible pérdida de enlace inminente". |
| `ALERT_SNR_WARN_DB` | 0 | PROVISIONAL | LoRa puede demodular con SNR negativo; el límite depende del factor de dispersión (SF). Un SNR ≤ 0 dB indica que el margen se está reduciendo. |
| `ALERT_HYSTERESIS_DB` | 3 | PROVISIONAL | Margen mayor que el ruido típico de las mediciones de RSSI/SNR; ajustable. |
| `ALERT_LINK_TIMEOUT_S` | 5 | PROVISIONAL | Varios periodos de transmisión supuestos de ~1 s (como el simulador). La frecuencia real de transmisión del CanSat **[PENDIENTE DE CONFIRMAR]**; si es menor, hay que aumentarlo. |
| `ALERT_INVALID_CONSECUTIVE` | 3 | PROVISIONAL | Una lectura aislada fuera de rango puede ser ruido; varias seguidas indican un problema. |
| `ALERT_DISCARD_WINDOW_S` / `ALERT_DISCARD_COUNT` | 10 / 3 | PROVISIONAL | Unos pocos descartes al inicio son normales (arranque del ESP32, línea cortada); tres en 10 s indican un problema sostenido. |

**Por qué son provisionales:** la sensibilidad y el SNR mínimo dependen de los parámetros LoRa configurados en el módulo (factor de dispersión, ancho de banda), que siguen **[PENDIENTE DE CONFIRMAR]** con el equipo del hardware. Los límites de demodulación por SF deben tomarse de la hoja de datos del fabricante del chip LoRa y de la documentación del módulo REYAX RYLR998 antes de fijar los valores definitivos en la tesis. Hasta entonces no deben presentarse como especificaciones del enlace.

Los valores en uso se consultan en `GET /api/alerts/config`. Un valor inválido (no numérico, `crit ≥ warn`, tiempo ≤ 0…) detiene el arranque del backend con un mensaje que nombra la variable.

Ejemplo (PowerShell):

```powershell
$env:ALERT_LINK_TIMEOUT_S = "10"
$env:ALERT_RSSI_WARN_DBM = "-95"
$env:ALERT_RSSI_CRIT_DBM = "-105"
uvicorn app.main:app --port 8000
```

## Mensaje de alertas (WebSocket y `GET /api/alerts`)

```json
{
  "type": "alerts",
  "link": "ok",
  "seconds_since_last_frame": 0.4,
  "active": [
    {"code": "LOW_SNR", "severity": "warning", "message": "...", "since": "2026-10-30T18:00:00+00:00"}
  ],
  "events": [
    {"code": "LOW_SNR", "severity": "warning", "state": "raised", "message": "...", "at": "..."}
  ],
  "diagnostics": {
    "port": "COM5", "baudrate": 115200,
    "frames_ok": 120, "frames_discarded": 2, "disconnects": 0, "last_error": null
  }
}
```

- `link`: `waiting` (sin tramas aún), `ok` o `lost`.
- `active`: críticas primero. `events`: la más reciente primero; `state` es `raised` o `cleared`.
- `diagnostics`: vacío con el simulador.

## Pruebas

Automáticas (`backend/tests/test_alerts.py`, sin hardware): configuración y validación de umbrales, niveles e histéresis de RSSI/SNR, estados del enlace, tiempo límite, datos inválidos, puerto no disponible, tramas descartadas, forma del mensaje, límite del historial y contadores de `SerialESP32` con `loop://`.

```bash
cd backend
python -m unittest discover -s tests -v
```

Manuales (criterios A6 y A8 de `DEVELOPMENT_PLAN.md`):

| ID | Prueba | Cómo | Resultado esperado |
|---|---|---|---|
| M1 | Señal débil en la demo | Modo simulador; observar el vuelo completo | Cerca del apogeo aparece `LOW_SNR` (el SNR simulado baja a −3 dB a 1000 m) y se resuelve durante el descenso; sin parpadeo |
| M2 | Pérdida de enlace | Modo serial con el sketch de prueba; desconectar el USB o apagar la ESP32 | `TRAMAS: PERDIDAS` y `LINK_LOST` en ≤ `ALERT_LINK_TIMEOUT_S` + 1 s; además `SERIAL_UNAVAILABLE` si el puerto desaparece; al reconectar ambas se resuelven |
| M3 | En espera | Backend en modo serial con la ESP32 sin transmitir | `TRAMAS: EN ESPERA`, sin `LINK_LOST` |
| M4 | Tramas corruptas | Sketch con `INJECT_BAD_FRAMES = true` (P7 de `PRUEBA_SERIAL.md`) | Contador "Descartadas" sube; `FRAME_ERRORS` solo si se acumulan 3 en 10 s |
| M5 | Reconexión del WebSocket | Detener y reiniciar el backend con el navegador abierto | Panel muestra "Sin conexión con el backend" y, al reconectar, vuelve a mostrar el estado actual (sin alertas obsoletas) |
| M6 | Configuración | Arrancar con `ALERT_RSSI_WARN_DBM=-120` y `ALERT_RSSI_CRIT_DBM=-110` | El backend no arranca y el error nombra `rssi_crit_dbm` / `rssi_warn_dbm` |

## Puntos abiertos

- **Parámetros LoRa y frecuencia de transmisión del CanSat [PENDIENTE DE CONFIRMAR]:** determinan los umbrales definitivos de RSSI, SNR y tiempo límite.
- **Persistencia de alertas por misión:** hoy no se guardan; si se necesitan para la consulta posterior, requeriría una tabla nueva.
- **Reloj "T. de misión" de la vista en vivo:** sigue pendiente (ver `PERSISTENCE.md`).
