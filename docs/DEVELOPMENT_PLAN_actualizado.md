# Plan de desarrollo incremental

## Objetivo

Construir progresivamente una estación terrena funcional para la recepción, procesamiento, visualización y análisis de telemetría CanSat.

## Incremento 0 — Preparación

Estado: COMPLETADO

Se creó la estructura `backend/` (FastAPI, telemetry package) y
`frontend/` (React + Vite), con dependencias fijadas en
`requirements.txt` y `package.json`.

Objetivo:

- Preparar estructura del proyecto.
- Configurar entorno.
- Definir arquitectura.
- Configurar backend y frontend base.
- Crear documentación del proyecto.

## Incremento 1 — Fuente de telemetría y backend

Estado: COMPLETADO

Se implementó `Simulator` (perfil de vuelo: ascenso suavizado ~35s,
apogeo a 1000 m, descenso bajo paracaídas a tasa constante, aterrizaje)
detrás de la interfaz `TelemetrySource`, y `processor.py` con validación
de rangos de sanidad y generación de advertencias. Probado con una
simulación completa de vuelo (90 lecturas) sin falsos positivos.

Objetivo:

Crear una fuente de datos simulada que genere telemetría y desarrollar el procesamiento inicial en Python.

Debe demostrar:

- Generación de datos.
- Recepción.
- Estructuración.
- Validación básica.
- Procesamiento.

## Incremento 2 — Comunicación en tiempo real

Estado: COMPLETADO

FastAPI expone `/ws/telemetry` (WebSocket, difunde cada lectura
procesada) y `/api/status` / `/api/telemetry/latest` (REST). Probado
con un cliente WebSocket real recibiendo el stream en vivo.

Objetivo:

Implementar FastAPI y WebSocket para enviar la telemetría procesada desde Python hacia React.

## Incremento 3 — Dashboard

Estado: COMPLETADO

Interfaz en React con encabezado de misión (estado de enlace, reloj,
contador de paquetes), hero de altitud/fase, y tarjetas con los valores
actuales de temperatura, presión, CO₂, RSSI y SNR (la tarjeta se resalta
si el valor viene marcado con advertencia por el backend).

Objetivo:

Crear la interfaz principal de la estación terrena.

Debe mostrar:

- Estado del sistema.
- Estado de recepción.
- Valores actuales.
- Información básica de telemetría.

## Incremento 4 — Gráficas en tiempo real

Estado: COMPLETADO

Gráficas en vivo (Recharts) de altitud, velocidad vertical, temperatura,
presión, RSSI y SNR, actualizadas conforme llegan datos por WebSocket.
Prototipo demostrable end-to-end verificado:

Datos simulados → Backend → Procesamiento → WebSocket → React → Visualización

Objetivo:

Representar las variables de telemetría mediante gráficas que se actualicen conforme llegan nuevos datos.

Al completar este incremento debe existir un prototipo demostrable del flujo:

Datos
→ Backend
→ Procesamiento
→ WebSocket
→ React
→ Visualización

## Incremento 5 — Comunicación UART real

Estado: IMPLEMENTADO (sin prueba con ESP32 físico)

Se añadió `SerialESP32` (`backend/app/telemetry/serial_esp32.py`) con
`parse_frame` aislado (formato confirmado en PROTOCOL.md: 9 campos
separados por coma). La fuente activa se elige con
`TELEMETRY_SOURCE=simulator|serial`; puerto y baudrate van por
`SERIAL_PORT` y `SERIAL_BAUDRATE` (obligatorios en modo serial).

Probado: parseo de tramas válidas e inválidas, lectura vía puerto
virtual `loop://` de pyserial, y puerto inexistente sin tumbar el
proceso. No hay ESP32 USB conectado en esta máquina (solo COM Bluetooth),
así que falta la prueba end-to-end con hardware real.

Verificado además con un puerto serial virtual del sistema operativo (no
`loop://`): lectura, descarte de tramas corruptas y con `nan`, guardado de
misión, CSV y recuperación tras desconexión del puerto. Para la prueba con la
ESP32 física se añadió `firmware/esp32_telemetria_prueba/` (generador de
tramas de prueba) y `docs/PRUEBA_SERIAL.md` (pruebas P1-P10 con criterios de
aceptación). Este incremento pasa a COMPLETADO al registrar esos resultados.

El simulador sigue siendo el predeterminado y no cambia su comportamiento.

Objetivo:

Sustituir la fuente simulada por la comunicación real con el ESP32 mediante puerto serial.

El formato exacto de la trama deberá confirmarse antes de implementar el parser definitivo.

## Incremento 6 — Persistencia

Estado: COMPLETADO

SQLite organizado por misión (`database.py`): una misión activa a la vez
(índice único parcial), inserción solo mientras la misión está activa, cierre
de misiones huérfanas al arrancar. Exportación a CSV por bloques
(`exporter.py`). API de misiones en `main.py`. En el frontend, `MissionPanel`
+ `useMissions` permiten iniciar/finalizar misiones y descargar el CSV.
Documentación en `PERSISTENCE.md`; pruebas en `backend/tests/test_database.py`.

Pendiente (Incremento 7): normalizar `sequence` y `mission_time_s` por misión.

Objetivo:

Implementar SQLite para almacenar sesiones y telemetría.

## Incremento 7 — Históricos y análisis

Estado: PENDIENTE

Objetivo:

Permitir consultar y analizar datos almacenados.

## Incremento 8 — Alertas y diagnóstico

Estado: PENDIENTE

Objetivo:

Implementar:

- Señal débil.
- Pérdida de comunicación.
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