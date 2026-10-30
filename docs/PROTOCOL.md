# Protocolo de telemetría

## Estado

EN DEFINICIÓN (parcialmente confirmado)

Este documento contiene únicamente información confirmada sobre el protocolo de comunicación entre el ESP32 y el software de la estación terrena.

## Medio de comunicación

- Interfaz: UART / puerto serial
- Dispositivo intermediario: ESP32
- Envío: `Serial.println(msg2);` — CONFIRMADA
- Terminador de trama: `\n` (salto de línea, producido por `println`) — CONFIRMADA
- Separador de campos: coma (`,`) — CONFIRMADA
- Número de campos por trama: 9 — CONFIRMADA
- Baudrate (ESP32 → PC por USB): 115200 — CONFIRMADA (`Serial.begin(115200)` en el código del receptor)

## Variables conocidas

`msg2` tiene la forma:

```
pass,value1,value2,value3,value4,value5,value6,rssi,snr
```

| Posición | Variable | Unidad | Estado |
|---|---|---|---|
| p0 | pass (identificador de trama) | N/A | Confirmada: cadena fija `571617` (código del receptor) |
| p1 | Temperatura | °C | Confirmada |
| p2 | Concentración de CO2 | ppm | Confirmada |
| p3 | Presión atmosférica | kPa | Confirmada |
| p4 | Altura | m | Confirmada |
| p5 | Aceleración total | m/s² | Confirmada |
| p6 | Velocidad | m/s | Confirmada |
| p7 | RSSI | dBm | Confirmada |
| p8 | SNR | dB | Confirmada |

**Nota:** esta correspondencia de posiciones reemplaza cualquier mapeo anterior
mencionado en versiones previas de este documento o de `PROJECT_CONTEXT.md`
(por ejemplo, una asociación previa de p0/p1/p2 con RSSI/SNR/Temperatura),
la cual era PROVISIONAL y queda descartada por esta información confirmada.

### Sobre `pass` (p0)

Confirmado (código del receptor, `String pass = "571617";`):
- Es el primer campo de la trama.
- Es una **cadena fija**: `571617`. No es un contador, un hash ni un valor calculado.
- Su función es verificar que la cadena llegó bien y evitar confundir valores si se amontonan paquetes en el puerto serial (el separador de paquetes es `\n`).
- El backend la valida: descarta las tramas cuyo `pass` no coincide (variable de entorno `FRAME_PASS`; ver `README.md`).

PENDIENTE DE CONFIRMAR:
- Si el valor cambiará en versiones futuras del firmware (en ese caso se ajusta `FRAME_PASS`).

### Sobre la unidad de Temperatura (p1)

Confirmada: la temperatura se transmite en grados Celsius (°C).

## Formato de trama

| Característica | Estado |
|---|---|
| Separador | CONFIRMADA — coma (`,`) |
| Terminador | CONFIRMADA — `\n` (vía `Serial.println`) |
| Encabezado adicional (antes de `pass`) | CONFIRMADA — no existe; `pass` es el primer campo de la trama |
| Número de campos | CONFIRMADA — 9 (`pass` + 6 valores + `rssi` + `snr`) |
| Unidad de temperatura | CONFIRMADA — °C |
| Tipo de dato de cada campo (texto/entero/flotante, precisión, decimales) | PENDIENTE |
| Checksum | PENDIENTE |
| CRC | PENDIENTE |
| Identificador de paquete (`pass`) | CONFIRMADA — cadena fija `571617`; validada por el backend |
| Timestamp | CONFIRMADA — no existe un campo de timestamp en la trama; los 9 campos listados arriba son la totalidad de la estructura confirmada |

No asumir, mientras sigan como PENDIENTE en la tabla anterior:

- Tipo de dato / precisión numérica de cada valor.
- Checksum.
- CRC.

## Lo que realmente llega por el puerto USB

Confirmado por el código del receptor:

- El receptor lee por `Serial2` una línea del módulo LoRa con 10 campos separados por coma: un prefijo de 5 caracteres (el código usa `substring(5, ...)`) seguido del ID del emisor, la longitud de los datos, los 6 valores, RSSI y SNR. Por USB solo reenvía `pass` + 6 valores + RSSI + SNR.
- Al arrancar (`setup()`, unos 10 s) imprime por el mismo puerto texto de configuración y las respuestas del módulo a los comandos AT. **No son tramas.**
- Si se conserva `Serial.println();` antes de cada trama, llega una línea vacía antes de cada paquete.
- El backend descarta todo lo que no tenga el formato de trama; las líneas vacías se omiten sin aviso.

## Fuente de información

El protocolo definitivo deberá obtenerse a partir del código/configuración real del ESP32 o de la documentación proporcionada para el CanSat.

Esta actualización proviene de información confirmada por el usuario sobre
el código fuente real del ESP32 (uso de `Serial.println(msg2)` con `msg2`
en el formato `pass,value1,value2,value3,value4,value5,value6,rssi,snr`).

El baudrate, el valor de `pass`, la unidad de temperatura y la estructura del receptor provienen del
código completo del receptor compartido por el usuario.

## Regla

No modificar este documento con información supuesta.

Toda característica del protocolo debe marcarse como:

- CONFIRMADA
- PENDIENTE
- PROVISIONAL

hasta contar con la información correspondiente.
