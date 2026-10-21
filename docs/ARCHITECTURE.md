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

El frontend no debe encargarse directamente de leer el puerto serial.

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

Protocolo confirmado (ver `PROTOCOL.md`): la trama del ESP32 es una línea de texto ASCII terminada en `\n` (enviada mediante `Serial.println`), con campos separados por comas. `SerialESP32` lee el puerto serial línea por línea (`readline()`) y `parse_frame` traduce la línea a `TelemetryReading`. Se rechazan las tramas con un número de campos distinto de 9 o con valores no numéricos o no finitos (`nan`, `inf`). El tipo de dato de cada campo, la unidad de temperatura y la validación de `pass` siguen PENDIENTES DE CONFIRMAR.

## 4. Comunicación backend/frontend

Para datos en tiempo real se utiliza WebSocket (`/ws/telemetry`).

Para misiones, consultas y exportación se utiliza una API HTTP mediante FastAPI (ver `PERSISTENCE.md`).

## 5. Base de datos

SQLite se usa para almacenamiento local (`backend/data/cansat.db`). La telemetría se guarda solo mientras hay una misión activa. El esquema, las reglas de funcionamiento y la exportación a CSV están documentados en `PERSISTENCE.md`.

## 6. Estado de la arquitectura

Este documento debe actualizarse cuando se modifique alguna decisión importante de arquitectura.

No documentar como definitivo aquello que todavía se encuentre pendiente de confirmar.
