# Prueba del enlace serial con la ESP32

Guía para comprobar que la estación terrena recibe, procesa, muestra y guarda
las tramas que la ESP32 envía por USB (UART). Los comandos están pensados para
Windows (PowerShell); en Linux/macOS cambian solo el puerto y la activación del
entorno virtual (ver `README.md`, Modo B).

## Qué ESP32 vas a usar

| Caso | Cuándo | Qué hace falta |
|---|---|---|
| **A. ESP32 de prueba** | Aún no tienes el CanSat o el receptor LoRa listos | Una ESP32 con el sketch `firmware/esp32_telemetria_prueba/` (emite el formato de `PROTOCOL.md` como un vuelo simulado) |
| **B. ESP32 real** | Ya tienes el receptor LoRa y el CanSat transmitiendo | El firmware real, que ejecuta `Serial.println(msg2)` |

El caso A prueba **el software** (puerto, parser, backend, dashboard, base de
datos, CSV). No prueba el enlace LoRa ni el firmware real.

## 1. Preparación (una vez)

1. Cable USB **de datos** (no solo de carga).
2. Driver del convertidor USB-serial de tu placa (CP210x o CH340, según el chip
   que veas en la placa). Si el puerto no aparece en el Administrador de
   dispositivos → Puertos (COM y LPT), instala el driver.
3. Instalación del backend y frontend según `README.md`.

## 2. Caso A: cargar el sketch de prueba

1. Arduino IDE → instala el soporte "esp32 by Espressif Systems" (Gestor de tarjetas).
2. Abre `firmware/esp32_telemetria_prueba/esp32_telemetria_prueba.ino`.
3. Placa: "ESP32 Dev Module" (o la tuya). Elige el puerto y pulsa Subir.
4. Abre el Monitor Serie a **115200** baudios: deben salir líneas como
   `TEST12,21.92,412,100.67,...` una vez por segundo.
5. **Cierra el Monitor Serie.** Si queda abierto, ocupa el puerto y el backend
   no podrá abrirlo.

Variables al inicio del sketch: `BAUDRATE` (debe coincidir con
`SERIAL_BAUDRATE`) e `INJECT_BAD_FRAMES` (ver prueba P7).

> El sketch fue verificado en un PC (sus tramas pasan `parse_frame`), pero no
> se compiló con el toolchain de Arduino-ESP32 en este entorno. Si el IDE marca
> un error de compilación, avísalo.

## 3. Pruebas

Ejecútalas en orden; no avances si una falla (la sección 5 ayuda a diagnosticar).

| ID | Prueba | Cómo | Resultado esperado |
|---|---|---|---|
| P1 | Puerto detectado | `python -m serial.tools.list_ports -v` con la ESP32 desconectada y luego conectada | Aparece un puerto nuevo (p. ej. `COM5`); ese es el tuyo |
| P2 | Lectura sin el sistema | `python tools/check_serial.py COM5 115200 --lines 15` (en `backend/`, venv activo) | Líneas `[OK]` consecutivas; solo la primera puede fallar |
| P3 | Baudrate incorrecto (prueba negativa) | `python tools/check_serial.py COM5 9600` | `[FALLA]` con caracteres `�`: el diagnóstico detecta el error |
| P4 | Backend en modo serial | Arranca el backend como en README, paso 5 (sin `--reload`) y abre `http://localhost:8000/api/status` | `"source_type": "SerialESP32"`, `"source_connected": true`; el log dice `puerto serial abierto` |
| P5 | Dashboard en vivo | `npm run dev`, abre `http://localhost:5173` | **Paquetes** sube cerca de 1 por segundo; valores y gráficas se mueven |
| P6 | Fidelidad de valores (caso A) | Deja correr ~40 s | Altitud llega a 1000 m hacia los 35 s; temperatura baja a ~15.5 en el apogeo; presión ~90 kPa |
| P7 | Tramas inválidas | En el sketch pon `INJECT_BAD_FRAMES = true`, vuelve a subirlo (cerrando el Monitor Serie) | El backend y el dashboard siguen funcionando; el log muestra `trama inválida descartada` (~1 de cada 10); **Paquetes** solo cuenta las válidas |
| P8 | Desconexión y reconexión | Desconecta el USB y vuelve a conectarlo **en el mismo puerto físico** | `source_connected` pasa a `false` y vuelve a `true` solo, sin reiniciar el backend |
| P9 | Misión y CSV | **Nueva misión**, espera 60 s, **Finalizar misión**, **Exportar CSV** y ábrelo en Excel | Muestras ≈ 60; acentos correctos; una fila por muestra |
| P10 | Estabilidad | Un vuelo completo del sketch (190 s) o 10 min de transmisión | Sin errores en el log; `sequence` continuo, sin saltos |

Notas:

- P8: en Windows el número COM puede cambiar si usas otro puerto USB; con otro
  número el backend no lo encuentra y hay que reiniciarlo con el puerto nuevo.
- P8 se verificó con un puerto virtual en Linux; en Windows con la ESP32 física
  está pendiente de confirmar.
- P3 y P7 son pruebas negativas: sirven para demostrar el manejo de errores.

## 4. Caso B: ESP32 real con el receptor LoRa

Las mismas pruebas, saltando la sección 2. Diferencias:

- El baudrate es el de `Serial.begin(...)` del firmware real (no se asume).
- Si el CanSat no está transmitiendo no llegan tramas; es normal. El indicador
  "ENLACE ACTIVO" solo dice que el navegador está conectado al backend.
- Si llegan líneas con otro formato (p. ej. respuestas del módulo LoRa), el
  backend las descarta y las registra en el log. Compáralas con
  `pass,v1,v2,v3,v4,v5,v6,rssi,snr` (`PROTOCOL.md`).
- Aparecerán avisos "fuera de rango" si los rangos de `processor.py` no
  corresponden a tu entorno; son orientativos y se pueden ajustar.

## 5. Si algo falla

| Síntoma | Causa probable |
|---|---|
| No aparece el puerto | Cable solo de carga o falta el driver |
| `No se pudo abrir COMx` / acceso denegado | Monitor Serie abierto u otro backend usando el puerto |
| Todo `[FALLA]` con `�` | Baudrate distinto al de `Serial.begin` |
| No llega ninguna línea | La ESP32 no transmite, o (caso B) el receptor no recibe del CanSat |
| El backend arranca pero el dashboard está en `--` | Aún no llegan tramas válidas: mira el log del backend |

Más casos en `README.md`, "Solución de problemas".

## 6. Qué no cubre esta prueba

- El algoritmo de `pass`, la unidad de temperatura y el tipo/precisión de los
  campos siguen **PENDIENTES DE CONFIRMAR** (`PROTOCOL.md`).
- No valida el enlace LoRa ni el alcance (~1 km).
- Las pruebas con el sketch no sustituyen una prueba con el firmware real.

## 7. Registro de resultados

| ID | Fecha | Caso (A/B) | Resultado | Observaciones |
|---|---|---|---|---|
| P1 | | | | |
| P2 | | | | |
| P3 | | | | |
| P4 | | | | |
| P5 | | | | |
| P6 | | | | |
| P7 | | | | |
| P8 | | | | |
| P9 | | | | |
| P10 | | | | |
