# Persistencia y exportación (Incremento 6)

## Alcance

- Almacenamiento de telemetría procesada en SQLite, organizada por **misión**.
- Una misión se inicia y se finaliza **manualmente** desde la GUI ("Nueva misión" / "Finalizar misión").
- Exportación de los datos de una misión a **CSV**.

Fuera de este incremento (Incremento 7): consulta de históricos dentro de la GUI, gráficas históricas, estadísticas y filtros.

## Reglas de funcionamiento

- Sin misión activa, los datos se muestran en vivo pero **no se guardan**.
- Solo puede haber **una misión activa** a la vez (lo impone un índice único parcial en la base de datos).
- Una lectura solo se inserta si su misión sigue activa en ese instante; no quedan muestras fuera del intervalo inicio–fin.
- Si el backend se apaga con una misión activa, al arrancar se **cierra** esa misión (`ended_at` = última lectura guardada, o el inicio si no hubo ninguna). No se reanuda, porque la fuente de datos también reinicia.
- Un fallo al guardar se registra en el log y **no interrumpe** la vista en vivo.

## Esquema

```text
missions   (id, name, notes, started_at, ended_at)            -- ended_at NULL = activa
telemetry  (id, mission_id → missions.id, sequence, mission_time_s, received_at,
            altitude_m, temperature_c, pressure_kpa, co2_ppm, velocity_ms,
            acceleration_ms2, rssi_dbm, snr_db, valid, warnings)
```

- `valid`: 1/0 según el procesador (`processor.py`).
- `warnings`: lista JSON de advertencias del procesador.
- Fechas en ISO 8601 UTC.

Archivo: `backend/data/cansat.db` (configurable con `DATABASE_PATH`). No debe versionarse en Git (`backend/.gitignore` ignora `data/`).

## API

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/missions` | Lista de misiones (más reciente primero) con `sample_count` |
| POST | `/api/missions` | Inicia una misión: `{"name": "...", "notes": "..."}` (409 si ya hay una activa) |
| POST | `/api/missions/{id}/end` | Finaliza la misión (404 si no existe, 409 si ya estaba finalizada) |
| GET | `/api/missions/{id}/export.csv` | Descarga el CSV de la misión |

`/api/status` incluye ahora `active_mission_id`.

## Formato del CSV

- UTF-8 con BOM, separador de campos coma, separador decimal punto, fin de línea CRLF.
- Columnas: `sequence, mission_time_s, received_at, altitude_m, temperature_c, pressure_kpa, co2_ppm, velocity_ms, acceleration_ms2, rssi_dbm, snr_db, valid, warnings`.
- `warnings` une las advertencias con ` | `.
- Nombre de archivo: `mision_<id>_<nombre>.csv`.

## Puntos abiertos

- **Unidad de temperatura [PENDIENTE DE CONFIRMAR]**: la columna se llama `temperature_c` porque así se nombra en todo el sistema, pero la unidad real del ESP32 sigue sin confirmarse (ver `PROTOCOL.md`).
- **`sequence` y `mission_time_s`** son los de la fuente de datos y **no se reinician** al crear una misión; una misión iniciada a mitad de un vuelo empieza con valores distintos de 0. Normalizarlos (tiempo relativo al inicio de la misión) se decide en el Incremento 7, cuando se grafiquen históricos.

## Frecuencia de lectura

- Con el `Simulator`, el ciclo del backend lee una trama por segundo (`TELEMETRY_INTERVAL_S`).
- Con `SerialESP32`, el ciclo **no espera** (`poll_interval_s = 0`): procesa y guarda cada trama válida en cuanto llega, sea cual sea la frecuencia de transmisión del CanSat. Así no se acumula retraso en el buffer serial.
- Se descartan (y se registran en el log) las tramas inválidas, incluidas las que traen `nan` o `inf`.
