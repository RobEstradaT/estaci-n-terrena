# Estación Terrena CanSat

Estación terrena para recibir, validar, guardar, visualizar y analizar la telemetría de un CanSat. Flujo completo:

```
CanSat → LoRa → receptor LoRa → ESP32 → UART/USB → backend Python
       → validación → WebSocket → React (en vivo)
                    → SQLite (si hay misión activa) → CSV / JSON
                    → análisis histórico por misión (React)
```

## Estado

| Prototipo | Estado |
|---|---|
| 1 Fuente simulada y procesamiento | Completado |
| 2 FastAPI + WebSocket | Completado |
| 3 Dashboard | Completado |
| 4 Gráficas en vivo | Completado |
| 5 UART real (`SerialESP32`) | Implementado; falta la prueba con el ESP32 físico |
| 6 Persistencia en SQLite + exportación CSV y JSON | Completado |
| 7 Análisis histórico | Implementado; pendiente de evaluación |
| 8 Alertas y diagnóstico | Implementado; pendiente de evaluación |
| 9 Pruebas finales y refinamiento | Pendiente |

El avance y los criterios de evaluación están en `docs/DEVELOPMENT_PLAN.md`.

## Requisitos

- **Python 3.10 o superior**
- **Node.js 20.19+ o 22.12+** (requisito de Vite 8)
- Para el modo real: un ESP32 conectado por USB (cable de **datos**, no solo de carga)

## Instalación (una sola vez)

```bash
# Backend
cd backend
python3 -m venv venv
source venv/bin/activate          # Windows PowerShell: venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Frontend
cd ../frontend
npm install
```

## Modo A — Simulador (demo sin hardware)

Es el modo predeterminado.

```bash
# Terminal 1
cd backend
source venv/bin/activate          # Windows: venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000

# Terminal 2
cd frontend
npm run dev
```

Abre `http://localhost:5173`. Verás un vuelo completo simulado (ascenso ~35 s, apogeo a 1000 m, descenso, aterrizaje). Reiniciar el backend repite el vuelo.

## Modo B — ESP32 real, paso a paso

### 1. Conecta el ESP32 y encuentra su puerto

El ESP32 es el que está unido al receptor LoRa y ejecuta `Serial.println(msg2)`.

```bash
cd backend
python -m serial.tools.list_ports -v
```

- **Windows:** `COM3`, `COM5`... (también en Administrador de dispositivos → Puertos). Ignora los "Enlace serie estándar" de Bluetooth: no son el ESP32.
- **Linux:** `/dev/ttyUSB0` o `/dev/ttyACM0`. Si da "Permission denied": `sudo usermod -aG dialout $USER` y vuelve a iniciar sesión.
- **macOS:** `/dev/cu.usbserial-*` o `/dev/cu.SLAB_USBtoUART`.

Truco: ejecuta el comando con el ESP32 desconectado y otra vez conectado; el puerto nuevo es el tuyo.

### 2. Averigua el baudrate

El baudrate del receptor está **confirmado: 115200** (`Serial.begin(115200)` en su código; ver `PROTOCOL.md`). El sistema no lo asume: siempre se indica con `SERIAL_BAUDRATE`. Si cambias el firmware, usa el valor de su `Serial.begin(...)`.

### 3. Libera el puerto

Solo un programa puede usar el puerto a la vez. Cierra el Monitor Serie de Arduino IDE/PlatformIO y cualquier otro backend que esté corriendo.

### 4. Prueba el enlace SIN levantar el sistema

```bash
cd backend
python tools/check_serial.py COM5 115200
```

(Sustituye puerto y baudrate.) Muestra cada trama como `[OK]` o `[FALLA]` con el motivo, y `AVISO` si algún valor sale de los rangos de sanidad. Lo esperado: varias líneas `[OK]` seguidas. Una falla en la primera línea es normal.

No avances hasta ver `[OK]`. La sección "Solución de problemas" cubre los fallos.

### 5. Arranca el backend en modo serial

Las variables solo valen para la terminal donde las defines.

**Windows (PowerShell):**
```powershell
cd backend
venv\Scripts\Activate.ps1
$env:TELEMETRY_SOURCE = "serial"
$env:SERIAL_PORT = "COM5"
$env:SERIAL_BAUDRATE = "115200"
uvicorn app.main:app --port 8000
```

**Windows (cmd):**
```bat
set TELEMETRY_SOURCE=serial
set SERIAL_PORT=COM5
set SERIAL_BAUDRATE=115200
uvicorn app.main:app --port 8000
```

**Linux / macOS:**
```bash
export TELEMETRY_SOURCE=serial SERIAL_PORT=/dev/ttyUSB0 SERIAL_BAUDRATE=115200
uvicorn app.main:app --port 8000
```

Usa `uvicorn` **sin `--reload`** con hardware: el recargador reinicia el proceso y puede dejar el puerto ocupado unos segundos.

En el log debe aparecer `puerto serial abierto: COM5 @ 115200 baud`. Si el ESP32 no estaba listo, el backend reintenta cada segundo solo.

**Espera unos 10 segundos antes de empezar:** al abrir el puerto, muchas placas ESP32 se reinician y el receptor tarda ~10 s en configurar el módulo LoRa (`setup()`); durante ese tiempo no reenvía tramas. Ver unas líneas de arranque descartadas en el log es normal.

### 6. Arranca el frontend

```bash
cd frontend
npm run dev
```

Abre `http://localhost:5173`.

### 7. Comprueba que los datos son reales

- `http://localhost:8000/api/status` debe mostrar `"source_type": "SerialESP32"` y `"source_connected": true`.
- En el dashboard, el contador **Paquetes** debe subir con cada trama recibida.
- **Ojo:** el indicador "ENLACE ACTIVO" del encabezado solo dice que el navegador está conectado al backend. **No** indica que el CanSat esté transmitiendo. La pérdida de señal del CanSat se indica con el indicador "TRAMAS" del encabezado y en el panel de alertas (Prototipo 8).

### 8. Graba una misión

Sin misión activa, los datos se ven pero **no se guardan**.

1. Escribe un nombre en el panel "Misión" y pulsa **Nueva misión** poco antes del lanzamiento.
2. El contador de muestras sube mientras graba.
3. Tras el aterrizaje pulsa **Finalizar misión**.
4. **Exportar CSV** o **JSON** descarga los datos (el CSV tiene BOM UTF-8 y abre bien en Excel).
5. **Analizar** muestra duración, estadísticas por variable y gráficas de la misión (Prototipo 7).

Los datos quedan en `backend/data/cansat.db`. Cópialo como respaldo después de cada prueba importante.

### Lista rápida para un día de pruebas

1. ESP32 conectado, Monitor Serie cerrado.
2. `check_serial.py` muestra `[OK]` consecutivos.
3. Backend en modo serial; `/api/status` con `source_connected: true`.
4. Frontend abierto; "Paquetes" sube.
5. **Nueva misión** antes del lanzamiento.
6. **Finalizar misión** después del aterrizaje.
7. Exportar CSV o JSON y respaldar `cansat.db`, y revisar el análisis.

## Variables de entorno

| Variable | Descripción | Predeterminado |
|---|---|---|
| `TELEMETRY_SOURCE` | `simulator` o `serial` | `simulator` |
| `SERIAL_PORT` | Puerto (obligatoria si `serial`) | — |
| `SERIAL_BAUDRATE` | Baudrate (obligatoria si `serial`; el receptor usa 115200) | — |
| `FRAME_PASS` | Valor esperado del campo `pass`; las tramas con otro valor se descartan. Vacío = no validar | `571617` |
| `DATABASE_PATH` | Ruta del archivo SQLite | `backend/data/cansat.db` |

## Pruebas automáticas (sin hardware)

```bash
cd backend
source venv/bin/activate
python -m unittest discover -s tests -v
```

Las pruebas están en `backend/tests/`: `test_parse_frame.py` (parser UART), `test_database.py` (misiones, telemetría, CSV y JSON) y `test_history.py` (tiempo por misión, migración, estadísticas y series).

## Solución de problemas

| Síntoma | Causa probable | Qué hacer |
|---|---|---|
| `No se pudo abrir COMx` / "Acceso denegado" | Otro programa usa el puerto, o puerto equivocado | Cierra Monitor Serie y otros backends; revisa `list_ports` |
| Todas las tramas `[FALLA]` con caracteres `�` | Baudrate distinto al de `Serial.begin` | Corrige `SERIAL_BAUDRATE` |
| No llega ninguna línea | ESP32 sin transmitir, cable solo de carga, o el receptor LoRa no recibe del CanSat | Revisa cable, alimenta el CanSat, mira el Monitor Serie del IDE (luego ciérralo) |
| "se esperaban 9 campos" | El formato de `msg2` difiere de `PROTOCOL.md` | Compara con `pass,v1,v2,v3,v4,v5,v6,rssi,snr` |
| "pass inválido" | El primer campo no es el esperado | Revisa `String pass` del firmware, o define `FRAME_PASS` (vacío = no validar) |
| "campo ... no numérico" / "no finito" | Texto, coma decimal, o `nan`/`inf` del sensor | Corrige en el firmware; el backend descarta esa trama |
| Líneas basura solo al inicio | Algunas placas se reinician al abrir el puerto y escriben su log de arranque | Normal; el backend las descarta |
| "TELEMETRY_SOURCE=serial requiere SERIAL_PORT y SERIAL_BAUDRATE" | Faltan variables | Defínelas en la misma terminal |
| Dashboard con "ENLACE ACTIVO" pero valores en `--` | Backend sin tramas válidas | Mira el log del backend |
| Muchos avisos "fuera de rango" | Los rangos de `processor.py` son orientativos | Ajusta `RANGES` (p. ej. altura si es sobre el nivel del mar) |
| Misión con 0 muestras | No llegan tramas válidas | Revisa `/api/status` y el log |
| Análisis muestra "--" en las estadísticas | La misión no tiene muestras válidas | Revisa que la misión haya recibido tramas (columna "Muestras") |

## Limitaciones conocidas (PENDIENTE DE CONFIRMAR)

- **Campo `pass`:** es una cadena fija (`571617`, confirmada en el firmware del receptor) y el backend la valida. No hay checksum ni CRC.
- **Tipo y precisión** de cada campo: se aceptan como `float`.
- **Reloj "T. de misión" en vivo:** usa el tiempo de la fuente; el análisis histórico usa el tiempo relativo a la misión, así que el cero no coincide entre ambas vistas.
- **Fase de misión** (ASCENSO, DESCENSO...): se infiere en el frontend; el CanSat no la transmite.
- **Umbrales de alertas:** provisionales hasta confirmar los parámetros LoRa y la frecuencia de transmisión (ver `docs/ALERTS.md`).

## Estructura

```
backend/
  app/            main.py, database.py, exporter.py, connection_manager.py
  app/telemetry/  source.py, simulator.py, serial_esp32.py, processor.py, schema.py
  tools/          check_serial.py
  tests/          test_parse_frame.py, test_database.py, test_history.py
frontend/src/     App.jsx, api.js, App.css, index.css
  components/     MissionPanel, MissionHistory, MissionHeader, AltitudeHero,
                  InstrumentGrid, InstrumentCard, TelemetryCharts (+ CSS)
  hooks/          useTelemetrySocket, useMissions, useMissionHistory
  utils/          missionPhase
docs/             PROJECT_CONTEXT, ARCHITECTURE, PROTOCOL, PERSISTENCE,
                  PRUEBA_SERIAL, DEVELOPMENT_PLAN
```
