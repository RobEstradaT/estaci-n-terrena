# Plan de desarrollo incremental

## Objetivo

Construir progresivamente una estación terrena funcional para la recepción, procesamiento, visualización y análisis de telemetría CanSat.

## Incremento 0 — Preparación

Estado: COMPLETADO

Se creó la estructura `backend/` (FastAPI, paquete `telemetry`) y
`frontend/` (React + Vite), con dependencias fijadas en
`requirements.txt` y `package.json`.

## Incremento 1 — Fuente de telemetría y backend

Estado: COMPLETADO

Se implementó `Simulator` (perfil de vuelo: ascenso suavizado ~35 s,
apogeo a 1000 m, descenso bajo paracaídas a tasa constante, aterrizaje)
detrás de la interfaz `TelemetrySource`, y `processor.py` con validación
de rangos de sanidad y generación de advertencias.

## Incremento 2 — Comunicación en tiempo real

Estado: COMPLETADO

FastAPI expone `/ws/telemetry` (WebSocket, difunde cada lectura
procesada) y `/api/status` / `/api/telemetry/latest` (REST).

## Incremento 3 — Dashboard

Estado: COMPLETADO

Interfaz en React con encabezado de misión (estado de enlace, reloj,
contador de paquetes), hero de altitud/fase, y tarjetas con los valores
actuales de temperatura, presión, CO₂, aceleración total, RSSI y SNR (la
tarjeta se resalta si el valor viene marcado con advertencia).

## Incremento 4 — Gráficas en tiempo real

Estado: COMPLETADO

Gráficas en vivo (Recharts) de altitud, velocidad vertical, temperatura,
presión, aceleración total, RSSI y SNR. Flujo verificado:

Datos simulados → Backend → Procesamiento → WebSocket → React → Visualización

## Incremento 5 — Comunicación UART real

Estado: IMPLEMENTADO (pendiente de prueba con ESP32 físico)

`SerialESP32` (`backend/app/telemetry/serial_esp32.py`) con `parse_frame`
aislado (formato confirmado en PROTOCOL.md: 9 campos separados por coma;
rechaza `nan`/`inf`). La fuente activa se elige con
`TELEMETRY_SOURCE=simulator|serial`; puerto y baudrate van por
`SERIAL_PORT` y `SERIAL_BAUDRATE` (obligatorios en modo serial).
El ciclo del backend no añade esperas con la fuente serial
(`poll_interval_s = 0`), para no acumular retraso.

Herramienta de diagnóstico: `backend/tools/check_serial.py` valida puerto,
baudrate y formato sin levantar el backend.

Probado sin hardware: parseo de tramas válidas e inválidas, lectura vía
puerto virtual `loop://` de pyserial y puerto inexistente sin tumbar el
proceso.

Pendiente: prueba end-to-end con el ESP32 físico; confirmar baudrate,
unidad de temperatura, algoritmo de `pass` y tipo de dato de los campos.

## Incremento 6 — Persistencia

Estado: COMPLETADO

SQLite organizado por misión (`database.py`): una misión activa a la vez
(índice único parcial), inserción solo mientras la misión está activa,
cierre de misiones huérfanas al arrancar. Exportación a CSV por bloques
(`exporter.py`). API de misiones en `main.py`. En el frontend,
`MissionPanel` + `useMissions` permiten iniciar/finalizar misiones y
descargar el CSV. Documentación en `PERSISTENCE.md`; pruebas en
`backend/tests/test_database.py`.

Pendiente (Incremento 7): normalizar `sequence` y `mission_time_s` por misión.

## Incremento 7 — Históricos y análisis

Estado: PENDIENTE

Objetivo:

Permitir consultar y analizar datos almacenados.

## Incremento 8 — Alertas y diagnóstico

Estado: PENDIENTE

Objetivo:

Implementar:

- Señal débil.
- Pérdida de comunicación (hoy el indicador "ENLACE ACTIVO" solo refleja la conexión navegador-backend).
- Datos inválidos.
- Errores seriales.
- Otras condiciones relevantes.

Los umbrales deberán ser configurables y estar técnicamente justificados.

## Incremento 9 — Pruebas y refinamiento

Estado: PENDIENTE

Objetivo:

- Pruebas del sistema.
- Manejo de errores.
- Mejoras de interfaz.
- Optimización.
- Documentación.
- Preparación para demostración final.

---

## Regla

Claude debe trabajar únicamente en el incremento solicitado.

No implementar automáticamente los incrementos posteriores.

Cuando termine un incremento, actualizar su estado y describir brevemente qué se completó y qué queda pendiente.
