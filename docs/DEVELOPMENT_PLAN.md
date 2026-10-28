# Plan de desarrollo por prototipos

Este documento sustituye a `DEVELOPMENT_PLAN_actualizado.md`, que debe eliminarse del repositorio.

## Objetivo

Construir progresivamente una estación terrena funcional para la recepción, procesamiento, visualización y análisis de telemetría CanSat.

## Metodología

El proyecto se desarrolla por **prototipos** (ver `REGLAS_ESTACION_TERRENA.md`, sección 2). Cada prototipo es una versión funcional y demostrable, con un objetivo y criterios de evaluación definidos antes de implementarse.

- Un prototipo no se da por cerrado si sus pruebas fallan o si su objetivo no se cumplió. En ese caso se documenta el motivo y se decide cómo seguir.
- Al terminar un prototipo se registran los resultados de su evaluación en este documento.
- Se trabaja únicamente en el prototipo solicitado. Los siguientes no se implementan por iniciativa propia.

La numeración de los prototipos es provisional hasta que se defina su alcance.

## Registro del desarrollo previo (metodología incremental, Incrementos 0–6)

Esta sección conserva el registro del trabajo realizado antes del cambio de metodología.

### Incremento 0 — Preparación

Estado: COMPLETADO

Se creó la estructura `backend/` (FastAPI, paquete `telemetry`) y `frontend/` (React + Vite), con dependencias fijadas en `requirements.txt` y `package.json`.

### Incremento 1 — Fuente de telemetría y backend

Estado: COMPLETADO

Se implementó `Simulator` (perfil de vuelo: ascenso suavizado ~35 s, apogeo a 1000 m, descenso bajo paracaídas a tasa constante, aterrizaje) detrás de la interfaz `TelemetrySource`, y `processor.py` con validación de rangos de sanidad y generación de advertencias.

### Incremento 2 — Comunicación en tiempo real

Estado: COMPLETADO

FastAPI expone `/ws/telemetry` (WebSocket, difunde cada lectura procesada) y `/api/status` / `/api/telemetry/latest` (REST).

### Incremento 3 — Dashboard

Estado: COMPLETADO

Interfaz en React con encabezado de misión (estado de enlace, reloj, contador de paquetes), hero de altitud/fase y tarjetas con los valores actuales de temperatura, presión, CO₂, aceleración total, RSSI y SNR. La tarjeta se resalta si el valor viene marcado con advertencia.

### Incremento 4 — Gráficas en tiempo real

Estado: COMPLETADO

Gráficas en vivo (Recharts) de altitud, velocidad vertical, temperatura, presión, aceleración total, RSSI y SNR.

Flujo verificado: datos simulados → backend → procesamiento → WebSocket → React → visualización.

### Incremento 5 — Comunicación UART real

Estado: IMPLEMENTADO, PENDIENTE DE PRUEBA CON ESP32 FÍSICO

`SerialESP32` (`backend/app/telemetry/serial_esp32.py`) con `parse_frame` aislado. Formato confirmado en `PROTOCOL.md`: 9 campos separados por coma. La fuente activa se elige con `TELEMETRY_SOURCE=simulator|serial`; puerto y baudrate van por `SERIAL_PORT` y `SERIAL_BAUDRATE`.

Probado con puerto virtual (`loop://` y puerto virtual del sistema operativo): parseo de tramas válidas e inválidas, descarte de tramas corruptas y con `nan`, y recuperación tras desconexión. El baudrate (115200) y el valor fijo de `pass` (`571617`) están confirmados en el código del receptor.

Pendiente: prueba end-to-end con el ESP32 físico, siguiendo `docs/PRUEBA_SERIAL.md` (pruebas P1–P11).

### Incremento 6 — Persistencia

Estado: COMPLETADO

SQLite organizado por misión (`database.py`): una misión activa a la vez (índice único parcial), inserción solo mientras la misión está activa y cierre de misiones huérfanas al arrancar. Exportación a CSV por bloques (`exporter.py`). En el frontend, `MissionPanel` y `useMissions` permiten iniciar, finalizar misiones y descargar el CSV. Documentación en `PERSISTENCE.md`; pruebas en `backend/tests/test_database.py`.

---

## Prototipo 1 — Análisis histórico (antes "Incremento 7")

Estado: IMPLEMENTADO, PENDIENTE DE EVALUACIÓN

**Objetivo:** permitir revisar una misión ya grabada. El tiempo y la secuencia se miden desde el inicio de cada misión, y la interfaz muestra estadísticas básicas y gráficas de la misión seleccionada.

**Alcance implementado:**

- `sequence` y `mission_time_s` calculados por misión al insertar, con migración única de datos anteriores (`PRAGMA user_version`).
- Endpoints `GET /api/missions/{id}/telemetry` (serie con muestreo) y `GET /api/missions/{id}/stats` (estadísticas).
- Vista "Analizar" en el panel de misiones: duración, muestras, inválidas, tabla de mínimo/promedio/máximo y gráficas.
- Pruebas automáticas en `backend/tests/test_history.py`.

**Criterios de evaluación:**

| ID | Criterio | Cómo se evalúa |
|---|---|---|
| C1 | La primera muestra de cada misión tiene `mission_time_s` ≈ 0 y `sequence` = 1, aunque el backend lleve horas encendido. | Automática |
| C2 | Una base de datos anterior se normaliza al abrirla, sin perder muestras. | Automática |
| C3 | Mínimo, promedio, máximo, duración y muestras inválidas coinciden con un cálculo independiente sobre el CSV exportado (p. ej. en Excel). | Manual |
| C4 | Una misión de 3600 muestras se consulta sin congelar la interfaz y cada gráfica usa como máximo 1000 puntos. | Manual (DevTools) |
| C5 | Una misión inexistente devuelve 404. Una misión sin muestras muestra un mensaje, sin error. | Automática y manual |
| C6 | La vista en vivo, el CSV y las misiones anteriores funcionan igual que antes (prueba P9 de `PRUEBA_SERIAL.md`). | Manual |

**Registro de evaluación:**

| Criterio | Fecha | Resultado | Observaciones |
|---|---|---|---|
| C1 | | | |
| C2 | | | |
| C3 | | | |
| C4 | | | |
| C5 | | | |
| C6 | | | |

**Pendientes (fuera de este prototipo):** filtro por rango de tiempo dentro de una misión; comparación entre dos misiones; reloj "T. de misión" de la vista en vivo relativo al inicio de la misión; eliminar misiones; estadísticas por fase de vuelo (requiere definir la fase, que hoy es solo visual).

---

## Prototipo 2 — Alertas y diagnóstico (antes "Incremento 8")

Estado: PENDIENTE

Objetivo preliminar: detectar y mostrar señal débil, pérdida de comunicación, datos inválidos, errores seriales y otras condiciones relevantes.

- La pérdida de comunicación no está cubierta hoy: el indicador "ENLACE ACTIVO" solo refleja la conexión navegador-backend, no la recepción de tramas.
- Los umbrales deberán ser configurables y estar técnicamente justificados.

Los criterios de evaluación se definirán antes de implementarse.

## Prototipo 3 — Pruebas finales y refinamiento (antes "Incremento 9")

Estado: PENDIENTE

Objetivo preliminar: pruebas del sistema, manejo de errores, mejoras de interfaz, optimización, documentación y preparación para la demostración final.

Los criterios de evaluación se definirán antes de implementarse.
