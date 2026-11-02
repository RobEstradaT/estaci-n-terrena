# Arquitectura del sistema

## 1. Arquitectura general

La estación terrena seguirá una arquitectura separada en backend y frontend.

```text
┌─────────────────────┐
│       CanSat        │
└──────────┬──────────┘
           │ LoRa
           ▼
┌─────────────────────┐
│   Receptor LoRa     │
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│        ESP32        │
└──────────┬──────────┘
           │ UART / USB
           ▼
┌─────────────────────┐
│   Backend Python    │
│                     │
│ Recepción           │
│ Validación          │
│ Procesamiento       │
│ Alertas             │
└──────┬────────┬─────┘
       │        │
       │        ▼
       │   ┌──────────┐
       │   │  SQLite  │
       │   └──────────┘
       │
       │ WebSocket / API
       ▼
┌─────────────────────┐
│    Frontend React   │
│                     │
│ Monitoreo           │
│ Gráficas            │
│ Históricos          │
│ Alertas             │
└─────────────────────┘
```

## 2. Separación de responsabilidades

### Backend

Responsable de:

- Comunicación serial.
- Recepción de datos.
- Reconstrucción de tramas.
- Validación.
- Procesamiento.
- Alertas y diagnóstico (`alerts.py`).
- Persistencia.
- API.
- WebSocket.
- Gestión de errores.

### Frontend

Responsable de:

- Interfaz de usuario.
- Visualización de valores.
- Gráficas.
- Indicadores de estado.
- Alertas visuales.
- Consulta y representación de información histórica.

El frontend no debe encargarse directamente de leer el puerto serial ni de decidir cuándo hay una alerta: solo muestra lo que el backend determina.

## 3. Fuente de datos

El backend utiliza una abstracción (`TelemetrySource`, en `backend/app/telemetry/source.py`) que permite trabajar con:

```text
Simulator
```

y con:

```text
SerialESP32
```

Ambas fuentes entregan al procesamiento una estructura de telemetría equivalente (`TelemetryReading`). Esto permite desarrollar y probar el sistema sin depender del hardware.

La fuente activa se elige con la variable de entorno `TELEMETRY_SOURCE` (`simulator` | `serial`); ver el README para el procedimiento completo.

Cada fuente declara en `poll_interval_s` cuánto debe esperar el ciclo del backend entre lecturas: el `Simulator` marca su propio ritmo (1 s) y `SerialESP32` usa 0, porque su `read()` ya bloquea hasta que llega una trama real.

Además, cada fuente puede exponer contadores de diagnóstico mediante `diagnostics()` (Prototipo 8): `SerialESP32` informa de tramas válidas, descartadas, desconexiones y último error; el `Simulator` devuelve un diccionario vacío. El resto del sistema solo depende de esa interfaz.

Protocolo confirmado (ver `PROTOCOL.md`): la trama del ESP32 es una línea de texto ASCII terminada en `\n` (enviada mediante `Serial.println`), con campos separados por comas. `SerialESP32` lee el puerto serial línea por línea (`readline()`) y `parse_frame` traduce la línea a `TelemetryReading`. Se rechazan las tramas con un número de campos distinto de 9, con `pass` distinto del esperado (`FRAME_PASS`) o con valores no numéricos o no finitos (`nan`, `inf`). El tipo de dato de cada campo, la unidad de temperatura (según `PROTOCOL.md`), checksum y CRC siguen PENDIENTES DE CONFIRMAR.

## 4. Comunicación backend/frontend

Para datos en tiempo real se utiliza WebSocket (`/ws/telemetry`). Por ese canal viajan dos tipos de mensaje:

- Lecturas procesadas (sin campo `type`), una por cada trama válida.
- Estado de alertas (`{"type": "alerts", ...}`), una vez por segundo y al conectarse un cliente.

Para misiones, consultas y exportación se utiliza una API HTTP mediante FastAPI (ver `PERSISTENCE.md`). El estado de alertas también puede consultarse por HTTP (`/api/alerts`, `/api/alerts/config`; ver `ALERTS.md`).

## 5. Base de datos

SQLite se usa para almacenamiento local (`backend/data/cansat.db`). La telemetría se guarda solo mientras hay una misión activa. El esquema, las reglas de funcionamiento y la exportación a CSV están documentados en `PERSISTENCE.md`. Las alertas no se guardan en la base de datos: viven en memoria.

## 6. Alertas y diagnóstico

El motor de alertas (`backend/app/alerts.py`) es independiente de FastAPI, WebSocket, SQLite y del puerto serial. Se alimenta desde dos puntos del backend:

- `telemetry_loop`: cada lectura procesada actualiza las alertas que dependen de su contenido (señal débil, SNR bajo, datos inválidos) y registra que el enlace está activo.
- `alerts_loop` (cada segundo): evalúa lo que no depende de que lleguen lecturas (pérdida de enlace, puerto serial, tramas descartadas) y difunde el estado a los clientes.

Un fallo en el motor se registra en el log y no interrumpe la telemetría en vivo ni el guardado. Los umbrales se configuran con variables de entorno `ALERT_*` y sus valores por omisión son provisionales (ver `ALERTS.md`).

## 7. Estado de la arquitectura

Este documento debe actualizarse cuando se modifique alguna decisión importante de arquitectura.

No documentar como definitivo aquello que todavía se encuentre pendiente de confirmar.
