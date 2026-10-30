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

Estado: IMPLEMENTADO, PENDIENTE DE EVALUACIÓN

**Objetivo:** que el operador sepa, sin interpretar números, cuándo el enlace con el CanSat se degrada o se pierde y cuándo la recepción tiene problemas. Detectar y mostrar señal débil, pérdida de comunicación, datos inválidos y errores seriales, con umbrales configurables y justificados.

**Alcance implementado:**

- Motor de alertas independiente (`backend/app/alerts.py`) con histéresis en RSSI/SNR, estado "en espera" antes de la primera trama y registro de eventos (activada/resuelta).
- Alertas: `WEAK_RSSI` (aviso y crítica), `LOW_SNR`, `LINK_LOST`, `INVALID_DATA`, `SERIAL_UNAVAILABLE` y `FRAME_ERRORS`.
- Umbrales configurables por variables de entorno `ALERT_*`, validados al arrancar. Valores por omisión PROVISIONALES (ver `ALERTS.md`).
- Contadores de diagnóstico en `SerialESP32` (`diagnostics()`): tramas válidas, descartadas, desconexiones y último error.
- Un mensaje `{"type": "alerts"}` por el WebSocket cada segundo, más `GET /api/alerts` y `GET /api/alerts/config`.
- Frontend: indicador "TRAMAS" en el encabezado (distinto de "ENLACE ACTIVO") y `AlertPanel` con alertas activas, diagnóstico y eventos recientes.
- Cambio en `processor.py`: la señal débil ya no vuelve inválida una lectura; se evalúa solo en el motor de alertas.
- Pruebas automáticas en `backend/tests/test_alerts.py`; pruebas manuales M1–M6 en `ALERTS.md`.

**Criterios de evaluación:**

| ID | Criterio | Cómo se evalúa |
|---|---|---|
| A1 | RSSI ≤ umbral de aviso genera `WEAK_RSSI` (aviso); ≤ umbral crítico, crítica. Una señal que oscila dentro del margen de histéresis no activa ni resuelve la alerta repetidamente. | Automática |
| A2 | Sin tramas válidas durante más de `ALERT_LINK_TIMEOUT_S` s se activa `LINK_LOST` (crítica) y se resuelve al llegar una trama. Antes de la primera trama el estado es "en espera" y no hay alerta. | Automática y manual (M2, M3) |
| A3 | Tras `ALERT_INVALID_CONSECUTIVE` lecturas inválidas seguidas se activa `INVALID_DATA`; una lectura válida la resuelve. Una señal débil por sí sola no vuelve inválida la lectura. | Automática |
| A4 | Un puerto serial no disponible o desconectado activa `SERIAL_UNAVAILABLE`; las tramas descartadas frecuentes activan `FRAME_ERRORS`; los contadores de diagnóstico reflejan tramas válidas, descartadas y desconexiones. | Automática y manual (M2, M4; P7 y P8 de `PRUEBA_SERIAL.md`) |
| A5 | Los umbrales se cambian con variables de entorno sin tocar el código; un valor inválido impide el arranque con un mensaje que nombra la variable. | Automática y manual (M6) |
| A6 | La interfaz muestra alertas activas, estado de las tramas y eventos recientes, se actualiza sin recargar, y al perder la conexión con el backend no deja alertas obsoletas. | Manual (M1, M5) |
| A7 | Sin regresión: la vista en vivo, las gráficas, las misiones, el CSV y el análisis funcionan igual que antes, y todas las pruebas automáticas existentes siguen pasando. | Automática y manual (P9 de `PRUEBA_SERIAL.md`, C6) |
| A8 | La pérdida de enlace aparece en pantalla en un máximo de `ALERT_LINK_TIMEOUT_S` + 1 s. | Manual (M2) |

**Registro de evaluación:**

| Criterio | Fecha | Resultado | Observaciones |
|---|---|---|---|
| A1 | | | |
| A2 | | | |
| A3 | | | |
| A4 | | | |
| A5 | | | |
| A6 | | | |
| A7 | | | |
| A8 | | | |

**Pendientes (fuera de este prototipo):** confirmar parámetros LoRa (SF, ancho de banda) y frecuencia de transmisión del CanSat para fijar los umbrales definitivos **[PENDIENTE DE CONFIRMAR]**; guardar las alertas por misión en SQLite; notificaciones sonoras.

## Prototipo 3 — Pruebas finales y refinamiento (antes "Incremento 9")

Estado: PENDIENTE

Objetivo preliminar: pruebas del sistema, manejo de errores, mejoras de interfaz, optimización, documentación y preparación para la demostración final.

Los criterios de evaluación se definirán antes de implementarse.
