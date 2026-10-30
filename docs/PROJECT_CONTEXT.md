# Proyecto: Estación Terrena CanSat

## 1. Descripción del proyecto

El proyecto consiste en desarrollar una estación terrena para la recepción, procesamiento, visualización y análisis de la telemetría de un satélite experimental tipo CanSat.

El desarrollo corresponde a un proyecto de tesis individual de la Licenciatura en Ciencias Computacionales.

El objetivo del software es recibir los datos de telemetría provenientes del CanSat, procesarlos y validarlos, almacenarlos y presentarlos mediante una interfaz gráfica que permita tanto el monitoreo en tiempo real como el análisis posterior de los datos.

## 2. Título del proyecto

"Desarrollo de una Estación Terrena para la recepción, procesamiento, visualización y análisis de la telemetría de un satélite experimental tipo CanSat."

## 3. Flujo general

El flujo esperado del sistema es:

CanSat
→ LoRa
→ Receptor LoRa
→ ESP32
→ UART / Puerto serial
→ Backend Python
→ Validación y procesamiento
→ SQLite
→ API / WebSocket
→ Frontend React
→ Visualización y análisis

## 4. Tecnologías

### Backend
- Python
- FastAPI
- pySerial
- WebSocket

### Frontend
- React
- Biblioteca de gráficas compatible con React, inicialmente considerar Recharts

### Base de datos
- SQLite

### Desarrollo
- Cursor
- Git

No utilizar XAMPP, MySQL, Apache ni PHP para este proyecto, salvo que posteriormente exista una razón técnica justificada para modificar esta decisión.

## 5. Variables de telemetría

Las variables que inicialmente deberá manejar el sistema son:

- Temperatura
- CO2
- Presión
- Altitud
- Velocidad
- RSSI
- SNR
- Aceleración total (confirmada mediante el protocolo real de la ESP32; no estaba contemplada en el alcance inicial de esta sección, ver `PROTOCOL.md`)

El ESP32 transmite los datos mediante UART. La trama real, confirmada a
partir del código fuente de la ESP32, se envía con `Serial.println(msg2)`,
donde `msg2` tiene la forma:

```
pass,value1,value2,value3,value4,value5,value6,rssi,snr
```

con la siguiente correspondencia CONFIRMADA (ver `PROTOCOL.md` para el
detalle completo y lo que sigue pendiente):

- p0 (`pass`) → identificador de trama (función confirmada; su
  generación y validación siguen **PENDIENTES DE CONFIRMAR**)
- p1 (`value1`) → Temperatura (°C)
- p2 (`value2`) → CO2 (ppm)
- p3 (`value3`) → Presión atmosférica (kPa)
- p4 (`value4`) → Altura (m)
- p5 (`value5`) → Aceleración total (m/s²)
- p6 (`value6`) → Velocidad (m/s)
- p7 (`rssi`) → RSSI (dBm)
- p8 (`snr`) → SNR (dB)

Esta correspondencia reemplaza cualquier mapeo anterior mencionado en
versiones previas de este documento (p. ej. una asociación provisional de
p0/p1/p2 con RSSI/SNR/Temperatura), la cual era PROVISIONAL.

IMPORTANTE: no inventar el algoritmo de `pass`,
el tipo de dato/precisión de cada valor, checksum ni CRC. Cuando esta
información no esté confirmada, marcarla como pendiente (ver `PROTOCOL.md`).

## 6. Funciones principales

La estación terrena deberá permitir posteriormente:

### Recepción
- Comunicación con el ESP32 mediante puerto serial.
- Lectura de tramas de telemetría.

### Procesamiento
- Reconstrucción de las tramas.
- Interpretación de los valores.
- Validación de formato y datos.
- Detección de valores inválidos o incompletos.

### Visualización
- Valores actuales de telemetría.
- Gráficas en tiempo real.
- Estado de comunicación.
- Indicadores de recepción.

### Almacenamiento
- Guardado de la telemetría en SQLite.
- Asociación de datos con sesiones o vuelos.

### Análisis histórico
- Consulta de datos previamente almacenados.
- Gráficas históricas.
- Estadísticas básicas.
- Filtros por sesión/vuelo.

### Alertas
- Señal débil.
- Pérdida de comunicación.
- Datos inválidos.
- Errores del puerto serial.
- Otras condiciones anormales que se definan posteriormente.

## 7. Prototipo inicial

Debido al tiempo limitado para presentar un avance funcional, el desarrollo inicial utilizará una fuente de datos simulada.

El prototipo deberá demostrar:

Datos simulados
→ Backend Python
→ Validación/procesamiento
→ WebSocket
→ React
→ Valores y gráficas en tiempo real

Posteriormente la fuente simulada será sustituida por la comunicación UART real del ESP32.

La arquitectura debe permitir realizar este cambio sin tener que rehacer el frontend.

## 8. Principio de desarrollo

El proyecto se desarrollará incrementalmente.

Cada incremento debe producir una parte funcional y comprobable del sistema.

No desarrollar toda la aplicación de una sola vez.

No avanzar automáticamente al siguiente incremento.

Cada incremento debe:

1. Explicar brevemente qué se realizará.
2. Implementar únicamente lo correspondiente a ese incremento.
3. Probar lo desarrollado.
4. Indicar cómo ejecutarlo.
5. Indicar qué se consiguió.
6. Indicar qué queda pendiente.

## 9. Calidad del código

Priorizar:

- Código claro.
- Modularidad.
- Simplicidad.
- Bajo acoplamiento.
- Separación entre backend y frontend.
- Manejo adecuado de errores.
- Facilidad de mantenimiento.
- Facilidad de explicación técnica para una tesis.

Evitar arquitecturas excesivamente complejas para las necesidades del proyecto.

## 10. Regla importante sobre información desconocida

Cuando falte información específica del CanSat, ESP32 o protocolo de comunicación:

NO inventarla.

Indicar claramente:

[PENDIENTE DE CONFIRMAR]

y continuar trabajando con una abstracción, simulación o configuración provisional cuando sea posible.

## 11. Documentación del contexto

Este archivo debe mantenerse actualizado durante el desarrollo cuando cambien decisiones importantes de arquitectura, tecnologías, protocolo o alcance.

Debe considerarse la fuente principal de contexto del proyecto.
