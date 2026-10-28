# Persistencia, exportación y análisis histórico (Incremento 6 y Prototipo 1)

## Alcance

- Almacenamiento de telemetría procesada en SQLite, organizada por **misión**.
- Una misión se inicia y se finaliza **manualmente** desde la GUI ("Nueva misión" / "Finalizar misión").
- Exportación de los datos de una misión a **CSV**.
- Análisis histórico de una misión finalizada: duración, muestras, estadísticas básicas y gráficas (Prototipo 1).

Fuera de este alcance (pendiente en prototipos posteriores): filtros por rango de tiempo, comparación entre misiones, eliminación de misiones y estadísticas por fase de vuelo.

## Reglas de funcionamiento

- Sin misión activa, los datos se muestran en vivo pero **no se guardan**.
- Solo puede haber **una misión activa** a la vez (lo impone un índice único parcial en la base de datos).
- Una lectura solo se inserta si su misión sigue activa en ese instante; no quedan muestras fuera del intervalo inicio–fin.
- Si el backend se apaga con una misión activa, al arrancar se **cierra** esa misión (`ended_at` = última lectura guardada, o el inicio si no hubo ninguna). No se reanuda, porque la fuente de datos también reinicia.
- Un fallo al guardar se registra en el log y **no interrumpe** la vista en vivo.

## Tiempo y secuencia por misión

`sequence` (1..N) y `mission_time_s` (segundos desde el inicio de la misión) se calculan **al insertar**; los valores de la fuente no se conservan. El cálculo se hace en la misma sentencia SQL que comprueba que la misión sigue activa, así que no hay carreras con "Finalizar misión".

- Cada misión empieza en `sequence = 1` y `mission_time_s ≈ 0`, sin importar cuándo se encendió el backend.
- Una lectura recibida justo antes de pulsar "Nueva misión" se guarda con `mission_time_s = 0` (nunca negativo).
- Las bases anteriores se normalizan **una sola vez** al abrirlas, controlando `PRAGMA user_version` (`DATA_VERSION = 1`). El resultado depende solo de `started_at` y `received_at`, así que es reproducible.
- El CSV conserva los mismos nombres de columna, pero `sequence` y `mission_time_s` ahora son relativos a la misión.

## Esquema

```text
missions   (id, name, notes, started_at, ended_at)            -- ended_at NULL = activa
telemetry  (id, mission_id → missions.id, sequence, mission_time_s, received_at,
            altitude_m, temperature_c, pressure_kpa, co2_ppm, velocity_ms,
            acceleration_ms2, rssi_dbm, snr_db, valid, warnings)
```

- `valid`: 1/0 según el procesador (`processor.py`).
- `warnings`: lista JSON de advertencias del procesador.
- Índices: `(mission_id, id)` para paginar y exportar, y `(mission_id, sequence)` para calcular la secuencia sin recorrer toda la misión.
- Fechas en ISO 8601 UTC.

Archivo: `backend/data/cansat.db` (configurable con `DATABASE_PATH`). No debe versionarse en Git (`backend/.gitignore` ignora `data/`).

## API

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/missions` | Lista de misiones (más reciente primero) con `sample_count` |
| POST | `/api/missions` | Inicia una misión: `{"name": "...", "notes": "..."}` (409 si ya hay una activa) |
| POST | `/api/missions/{id}/end` | Finaliza la misión (404 si no existe, 409 si ya estaba finalizada) |
| GET | `/api/missions/{id}/export.csv` | Descarga el CSV de la misión |
| GET | `/api/missions/{id}/telemetry?max_points=1000` | Serie para gráficas. Si hay más puntos que `max_points`, muestrea 1 de cada `step` y devuelve `total` y `step` (`max_points` entre 10 y 5000) |
| GET | `/api/missions/{id}/stats` | Duración, muestras, inválidas y mínimo/promedio/máximo por variable (404 si la misión no existe; una misión sin muestras devuelve `null` en los valores) |

`/api/status` incluye `active_mission_id`.

## Formato del CSV

- UTF-8 con BOM, separador de campos coma, separador decimal punto, fin de línea CRLF.
- Columnas: `sequence, mission_time_s, received_at, altitude_m, temperature_c, pressure_kpa, co2_ppm, velocity_ms, acceleration_ms2, rssi_dbm, snr_db, valid, warnings`.
- `warnings` une las advertencias con ` | `.
- Nombre de archivo: `mision_<id>_<nombre>.csv`.

## Puntos abiertos

- **Unidad de temperatura [PENDIENTE DE CONFIRMAR]**: la columna se llama `temperature_c` porque así se nombra en todo el sistema, pero la unidad real del ESP32 sigue sin confirmarse (ver `PROTOCOL.md`).
- **Reloj "T. de misión" de la vista en vivo**: sigue mostrando el tiempo de la fuente, no el tiempo relativo a la misión. Por eso, en vivo y en el análisis, el cero no coincide. Pendiente.

## Frecuencia de lectura

- Con el `Simulator`, el ciclo del backend lee una trama por segundo (`TELEMETRY_INTERVAL_S`).
- Con `SerialESP32`, el ciclo **no espera** (`poll_interval_s = 0`): procesa y guarda cada trama válida en cuanto llega, sea cual sea la frecuencia de transmisión del CanSat. Así no se acumula retraso en el buffer serial.
- Se descartan (y se registran en el log) las tramas inválidas, incluidas las que traen `nan` o `inf`.
