# Plan de desarrollo incremental

## Objetivo

Construir progresivamente una estación terrena funcional para la recepción, procesamiento, visualización y análisis de telemetría CanSat.

## Incremento 0 — Preparación

Estado: PENDIENTE

Objetivo:

- Preparar estructura del proyecto.
- Configurar entorno.
- Definir arquitectura.
- Configurar backend y frontend base.
- Crear documentación del proyecto.

## Incremento 1 — Fuente de telemetría y backend

Estado: PENDIENTE

Objetivo:

Crear una fuente de datos simulada que genere telemetría y desarrollar el procesamiento inicial en Python.

Debe demostrar:

- Generación de datos.
- Recepción.
- Estructuración.
- Validación básica.
- Procesamiento.

## Incremento 2 — Comunicación en tiempo real

Estado: PENDIENTE

Objetivo:

Implementar FastAPI y WebSocket para enviar la telemetría procesada desde Python hacia React.

## Incremento 3 — Dashboard

Estado: PENDIENTE

Objetivo:

Crear la interfaz principal de la estación terrena.

Debe mostrar:

- Estado del sistema.
- Estado de recepción.
- Valores actuales.
- Información básica de telemetría.

## Incremento 4 — Gráficas en tiempo real

Estado: PENDIENTE

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

Objetivo:

Sustituir la fuente simulada por la comunicación real con el ESP32 mediante puerto serial.

El formato exacto de la trama deberá confirmarse antes de implementar el parser definitivo.

## Incremento 6 — Persistencia

Estado: PENDIENTE

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