# Reglas de trabajo — Estación Terrena CanSat

Este archivo resume las reglas que seguimos en el proyecto. Úsalo como contexto
al inicio de cada conversación. Las fuentes de verdad del proyecto son los
documentos en `docs/` (sobre todo `PROJECT\\\_CONTEXT.md`, `PROTOCOL.md` y
`DEVELOPMENT\\\_PLAN.md`). Si este archivo y esos documentos se contradicen, prevalecen
los documentos y este archivo debe actualizarse.

## 1\. Contexto y alcance

* Proyecto de tesis de Ciencias Computacionales (UAEH) sobre una estación terrena
para recibir, procesar, validar, visualizar y consultar telemetría de un CanSat.
Compite en una convocatoria organizada por la UNAM.
* El alcance es exclusivamente de software y de la estación terrena. El hardware del
CanSat (estructura, sensores, sistema de descenso) lo desarrolla un equipo externo.
* Flujo de referencia:
CanSat → LoRa → receptor LoRa → ESP32 → UART/USB → backend Python → validación
→ SQLite (si hay misión activa) → API/WebSocket → React → visualización y consulta.
* Stack: Python, FastAPI, pySerial, SQLite, WebSocket; React con Vite y Recharts.
No usar XAMPP, MySQL, Apache ni PHP.
* Pendiente de entrega de la tesis: inicios de diciembre.

## 2\. Metodología: prototipado

* El proyecto se desarrolla por **prototipos**. Cada prototipo es una versión
funcional y demostrable del sistema, con un objetivo y criterios de evaluación
definidos antes de empezar.
* Trabajar únicamente en el prototipo solicitado. No implementar el siguiente por
iniciativa propia.
* Al terminar un prototipo, registrar qué se evaluó, qué resultados se obtuvieron y
qué cambios quedan pendientes. Los hallazgos se reflejan en la documentación
(`DEVELOPMENT\\\_PLAN.md`, `PROTOCOL.md`, README), no solo en el chat.
* Cada prototipo debe seguir esta secuencia:

  1. Explicar brevemente su objetivo y los criterios de evaluación.
  2. Implementar solo lo que corresponde a ese prototipo.
  3. Probarlo (pruebas automáticas y, cuando aplique, pruebas manuales).
  4. Indicar cómo ejecutarlo.
  5. Indicar qué se logró y qué queda pendiente.
* Los prototipos pueden repetirse o refinarse a partir de la evaluación. Un prototipo
no se da por cerrado si sus pruebas fallan o si su objetivo no se cumplió; en ese
caso se documenta el motivo y se decide cómo seguir.
* Estado de avance (registro en `docs/DEVELOPMENT_PLAN.md`):

  * Completados: Prototipo 1 (fuente simulada y procesamiento), 2 (comunicación en
tiempo real), 3 (dashboard), 4 (gráficas en vivo) y 6 (persistencia con exportación
CSV y JSON).
  * Prototipo 5 (comunicación serial real, `SerialESP32`): implementado y probado con
puerto virtual. Pendiente la prueba con ESP32 físico (ver `docs/PRUEBA_SERIAL.md`).
  * Prototipos 7 (análisis histórico) y 8 (alertas y diagnóstico): implementados,
pendientes de evaluación.
  * Pendiente: Prototipo 9 (pruebas finales y refinamiento).

## 3\. Información no confirmada

* No inventar datos del CanSat, del ESP32 ni del protocolo.
* Marcar lo desconocido como `\\\[PENDIENTE DE CONFIRMAR]` y, cuando sea posible,
continuar con una abstracción, simulación o configuración provisional.
* Clasificar las características del protocolo como CONFIRMADA, PENDIENTE o
PROVISIONAL en `PROTOCOL.md`. No modificar ese documento con suposiciones.
* Pendientes actuales: tipo de dato y precisión de cada campo, checksum, CRC y
algoritmo de generación del campo `pass`. Ya están confirmados: el baudrate
(115200), el valor fijo de `pass` (`571617`) y la unidad de temperatura (°C).

## 4\. Protocolo y trama

* Trama: `pass,value1,value2,value3,value4,value5,value6,rssi,snr`, terminada en `\\\\n`,
campos separados por coma, 9 campos.
* Mapeo confirmado: p0 `pass` · p1 temperatura (°C) · p2 CO₂ (ppm) · p3 presión (kPa)
· p4 altura (m) · p5 aceleración total (m/s²) · p6 velocidad (m/s) · p7 RSSI (dBm)
· p8 SNR (dB).
* El backend valida `pass` mediante la variable `FRAME\\\_PASS` (predeterminado `571617`;
vacío = no validar).
* Las tramas inválidas (número de campos incorrecto, valor no numérico, `nan`, `inf`,
`pass` distinto) se descartan y se registran en el log. Nunca deben tumbar el proceso.
* Las líneas vacías se omiten sin aviso.

## 5\. Arquitectura y separación de responsabilidades

* El backend se encarga de la recepción, validación, procesamiento, persistencia,
API y WebSocket. El frontend no lee el puerto serial.
* Toda fuente de telemetría implementa `TelemetrySource`. El resto del sistema no debe
depender de si los datos vienen del `Simulator` o de `SerialESP32`.
* `parse\\\_frame` es una función aislada. Cambiar el formato de la trama solo debe
tocar ese punto.
* Lo bloqueante (apertura del puerto, `readline()`, escrituras a SQLite) va en
`asyncio.to\\\_thread`. No se bloquea el event loop.
* Cada operación de SQLite abre su propia conexión.
* Solo puede haber una misión activa a la vez; la base de datos lo garantiza con un
índice único parcial.
* Con una misión activa, se guarda cada lectura. Si una escritura falla, se registra y
no interrumpe la vista en vivo.
* Con `SerialESP32`, `poll\\\_interval\\\_s = 0`. El simulador usa 1 s. No añadir esperas que
acumulen retraso.
* Sin misión activa, los datos se muestran en vivo pero no se guardan.

## 6\. Simulación primero

* El `Simulator` es la fuente predeterminada y permite desarrollar y probar todo el
pipeline sin hardware. No se elimina ni cambia su comportamiento al añadir nuevas
fuentes.
* Los valores del simulador y los rangos de `processor.py` son provisionales y
orientativos. No deben presentarse como especificaciones del CanSat.
* La fase de misión (ASCENSO, APOGEO, etc.) se infiere en el frontend. Debe tratarse
como ayuda visual, no como dato del protocolo.

## 7\. Calidad del código

* Priorizar código claro, modular, simple y con bajo acoplamiento.
* Evitar arquitecturas más complejas de lo que el proyecto necesita. En un prototipo,
la solución más simple que cumpla el objetivo es la preferida.
* Manejar los errores de forma explícita. Las excepciones de dominio tienen tipo propio
(`InvalidFrameError`, `MissionNotFoundError`, `MissionStateError`).
* Cada cambio de comportamiento debe venir con pruebas en `backend/tests/`. Las pruebas
se ejecutan con `python -m unittest discover -s tests -v`.
* Las pruebas no deben depender de hardware. Para el puerto serial se usan `loop://` o
puertos virtuales.
* El código y los nombres de variables van en inglés o en el idioma que ya use el archivo.
Los mensajes para el usuario, la GUI y la documentación van en español.
* Frontend: usar los tokens de `index.css` (colores y tipografías); no introducir
estilos ajenos al sistema visual.
* Lint: `oxlint` en el frontend.

## 8\. Documentación

* Mantener actualizados `PROJECT\\\_CONTEXT.md`, `ARCHITECTURE.md`, `PROTOCOL.md`,
`PERSISTENCE.md`, `DEVELOPMENT\\\_PLAN.md` y el `README.md` cuando cambie una decisión
importante de arquitectura, tecnología, protocolo, metodología o alcance.
* No documentar como definitivo lo que aún está pendiente de confirmar.
* Separar alcance (delimitaciones factuales, p. ej. "la validación se hace con datos
simulados") de limitaciones (causas externas y sus consecuencias, p. ej. entregas de
hardware). Evitar repetir el mismo contenido en ambas secciones.
* La metodología de prototipado debe reflejarse en el capítulo metodológico de la tesis
(1.2) con la misma terminología.

## 9\. Forma de explicar y de entregar

* Preferir explicaciones concretas y específicas del proyecto, no genéricas.
* Trabajar en pasos: primero el concepto, después su aplicación al proyecto, y por
último corregir y depurar.
* Ser preciso. Señalar redundancias estructurales y errores, incluso en texto
redactado por IA.
* Cuando se pida una corrección, indicar explícitamente qué cambió y por qué.
* Para la tesis: redactar en español, con buena estructura y fuentes confiables,
reconocidas y consultables. Dejar de usar citas IEEE (números entre corchetes) para ahora usar citas convencionales (apellidos de autor y año)
Parafrasear con cita; no copiar textualmente. Para el estado del arte, indicar qué
trabajos se usaron y su enlace.
* Verificar contra fuentes primarias (documentación oficial, código real) antes de
afirmar algo sobre tecnologías o protocolos.

## 10\. Entorno de desarrollo

* Windows 11. Editor: Cursor. Control de versiones: Git y GitHub.
* Comandos de Windows en PowerShell salvo que se indique otra cosa.
* Desarrollo con dos terminales: `uvicorn app.main:app --port 8000` (sin `--reload`
cuando se usa hardware) y `npm run dev` para el frontend.
* `backend/data/` (la base de datos) no se versiona. Respaldar `cansat.db` después de
cada prueba importante.
* Hardware de prueba: ESP32 con el sketch `firmware/esp32\\\_telemetria\\\_prueba/`. El
equipo de la máquina solo expone puertos Bluetooth, así que la prueba con ESP32 USB
requiere conectar el dispositivo físicamente.

## 11\. Cómo cerrar una sesión de trabajo

Antes de terminar, comprobar:

* Las pruebas pasan.
* Los documentos afectados están actualizados.
* Se indicó qué se logró, qué se evaluó y qué queda pendiente.
* Se dejó claro qué sigue sin confirmar (`\\\[PENDIENTE DE CONFIRMAR]`).

