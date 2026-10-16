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

## Variables conocidas

`msg2` tiene la forma:

```
pass,value1,value2,value3,value4,value5,value6,rssi,snr
```

| Posición | Variable | Unidad | Estado |
|---|---|---|---|
| p0 | pass (identificador de trama) | N/A | Confirmada (función); generación/validación PENDIENTE |
| p1 | Temperatura | PENDIENTE | Confirmada (variable); unidad PENDIENTE |
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

Confirmado:
- Es el primer campo de la trama.
- Su función es ayudar a identificar/verificar la cadena y evitar confusión entre paquetes.

PENDIENTE DE CONFIRMAR (no asumir nada de lo siguiente):
- Algoritmo de generación.
- Valor o rango de valores posible.
- Longitud / tipo de dato.
- Si es un contador secuencial, un valor fijo, un hash, u otro mecanismo.
- Mecanismo de validación en el backend.

### Sobre la unidad de Temperatura (p1)

Confirmado: existe una variable de temperatura en la posición p1.
PENDIENTE DE CONFIRMAR: su unidad (no asumir Celsius, Fahrenheit ni Kelvin).

## Formato de trama

| Característica | Estado |
|---|---|
| Separador | CONFIRMADA — coma (`,`) |
| Terminador | CONFIRMADA — `\n` (vía `Serial.println`) |
| Encabezado adicional (antes de `pass`) | CONFIRMADA — no existe; `pass` es el primer campo de la trama |
| Número de campos | CONFIRMADA — 9 (`pass` + 6 valores + `rssi` + `snr`) |
| Tipo de dato de cada campo (texto/entero/flotante, precisión, decimales) | PENDIENTE |
| Checksum | PENDIENTE |
| CRC | PENDIENTE |
| Identificador de paquete (algoritmo de `pass`) | PENDIENTE |
| Timestamp | CONFIRMADA — no existe un campo de timestamp en la trama; los 9 campos listados arriba son la totalidad de la estructura confirmada |

No asumir, mientras sigan como PENDIENTE en la tabla anterior:

- Tipo de dato / precisión numérica de cada valor.
- Checksum.
- CRC.
- Algoritmo, tipo o validación de `pass`.

## Fuente de información

El protocolo definitivo deberá obtenerse a partir del código/configuración real del ESP32 o de la documentación proporcionada para el CanSat.

Esta actualización proviene de información confirmada por el usuario sobre
el código fuente real del ESP32 (uso de `Serial.println(msg2)` con `msg2`
en el formato `pass,value1,value2,value3,value4,value5,value6,rssi,snr`).

## Regla

No modificar este documento con información supuesta.

Toda característica del protocolo debe marcarse como:

- CONFIRMADA
- PENDIENTE
- PROVISIONAL

hasta contar con la información correspondiente.
