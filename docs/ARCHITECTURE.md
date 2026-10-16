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

El backend debe utilizar una abstracción que permita trabajar inicialmente con:

```text
Simulator
```

y posteriormente con:

```text
SerialESP32
```

Ambas fuentes deben entregar al procesamiento una estructura de telemetría equivalente.

Esto permitirá desarrollar y probar el sistema sin depender inicialmente del hardware.

Nota confirmada por el protocolo real (ver `PROTOCOL.md`): la trama del
ESP32 es una línea de texto ASCII terminada en `\n` (enviada mediante
`Serial.println`), con campos separados por comas. Esto implica que
`SerialESP32` deberá leer el puerto serial línea por línea (p. ej.
`readline()`), no por conteo fijo de bytes ni por un protocolo binario.
El parseo concreto de esa línea (`parse_frame`) se implementará en el
Incremento 5 y no se adelanta aquí; el tipo de dato de cada campo y la
validación de `pass` siguen PENDIENTES DE CONFIRMAR.

## 4. Comunicación backend/frontend

Para datos en tiempo real se utilizará WebSocket.

Para consultas históricas y operaciones convencionales se podrá utilizar una API HTTP mediante FastAPI.

## 5. Base de datos

SQLite será utilizada para almacenamiento local.

La estructura definitiva se establecerá durante el incremento correspondiente a persistencia.

## 6. Estado de la arquitectura

Este documento debe actualizarse cuando se modifique alguna decisión importante de arquitectura.

No documentar como definitivo aquello que todavía se encuentre pendiente de confirmar.