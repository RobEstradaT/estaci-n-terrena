"""
Persistencia en SQLite (Incremento 6; análisis histórico en el Prototipo 1).

Responsabilidad: guardar misiones y lecturas de telemetría ya procesadas
(el `dict` que produce `ProcessedTelemetry.to_dict()`), devolverlas cuando
se consulten y calcular estadísticas y series para el análisis. No conoce
FastAPI, WebSocket ni la fuente de datos.

Decisiones de diseño:
- Solo se guarda mientras hay una misión activa; la misión se inicia y se
  finaliza manualmente desde la GUI.
- Solo puede haber una misión activa a la vez. Lo garantiza la propia base
  de datos (índice único parcial), no solo el código de la aplicación.
- Cada operación abre su propia conexión: sqlite3 no permite compartir una
  conexión entre hilos y el backend llama a esta clase desde
  `asyncio.to_thread` para no bloquear el event loop.
- Una lectura solo se inserta si su misión sigue activa en ese instante,
  así nunca quedan muestras fuera del intervalo [inicio, fin] de la misión.
- `sequence` (1..N) y `mission_time_s` (segundos desde el inicio de la misión)
  se calculan al insertar, no se toman de la fuente. Así cada misión empieza
  en 0 sin importar cuándo se encendió el backend.
"""

from __future__ import annotations

import json
import math
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

# backend/data/cansat.db (se puede cambiar con la variable DATABASE_PATH).
DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "cansat.db"

# Variables numéricas de telemetría que se guardan; mismos nombres que
# `TelemetryReading` (schema.py) para no traducir nada al insertar.
TELEMETRY_FIELDS = (
    "altitude_m",
    "temperature_c",
    "pressure_kpa",
    "co2_ppm",
    "velocity_ms",
    "acceleration_ms2",
    "rssi_dbm",
    "snr_db",
)

# Columnas que se devuelven en las series para las gráficas.
SERIES_COLUMNS = ("sequence", "mission_time_s", "valid", *TELEMETRY_FIELDS)

# Versión de los datos guardados. 1 = `sequence` y `mission_time_s` relativos
# a cada misión. Las bases anteriores se normalizan al abrirlas.
DATA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS missions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    notes      TEXT,
    started_at TEXT NOT NULL,
    ended_at   TEXT
);

-- Como mucho una fila con ended_at NULL (misión activa) a la vez.
CREATE UNIQUE INDEX IF NOT EXISTS idx_one_active_mission
    ON missions ((ended_at IS NULL)) WHERE ended_at IS NULL;

CREATE TABLE IF NOT EXISTS telemetry (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_id       INTEGER NOT NULL REFERENCES missions(id) ON DELETE CASCADE,
    sequence         INTEGER NOT NULL,
    mission_time_s   REAL NOT NULL,
    received_at      TEXT NOT NULL,
    altitude_m       REAL NOT NULL,
    temperature_c    REAL NOT NULL,
    pressure_kpa     REAL NOT NULL,
    co2_ppm          REAL NOT NULL,
    velocity_ms      REAL NOT NULL,
    acceleration_ms2 REAL NOT NULL,
    rssi_dbm         REAL NOT NULL,
    snr_db           REAL NOT NULL,
    valid            INTEGER NOT NULL,
    warnings         TEXT NOT NULL DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS idx_telemetry_mission
    ON telemetry (mission_id, id);

CREATE INDEX IF NOT EXISTS idx_telemetry_mission_seq
    ON telemetry (mission_id, sequence);
"""

_MISSION_SELECT = """
SELECT m.id, m.name, m.notes, m.started_at, m.ended_at,
       (SELECT COUNT(*) FROM telemetry t WHERE t.mission_id = m.id) AS sample_count
FROM missions m
"""

# Columnas de valores de una lectura (sin mission_id, sequence ni mission_time_s).
_VALUE_COLUMNS = ("received_at", *TELEMETRY_FIELDS, "valid", "warnings")
_VALUE_COLUMNS_SQL = ", ".join(_VALUE_COLUMNS)
_VALUE_PLACEHOLDERS = ", ".join("?" for _ in _VALUE_COLUMNS)

# Inserta solo si la misión sigue activa. `sequence` y `mission_time_s` se
# calculan en la misma sentencia, así que no hay carrera con end_mission().
# MAX(0.0, ...) evita tiempos negativos si una lectura se recibió justo antes
# de que se pulsara "Nueva misión".
_INSERT_TELEMETRY_SQL = (
    f"INSERT INTO telemetry (mission_id, sequence, mission_time_s, {_VALUE_COLUMNS_SQL}) "
    "SELECT m.id, "
    "(SELECT COALESCE(MAX(t.sequence), 0) + 1 FROM telemetry t WHERE t.mission_id = m.id), "
    "MAX(0.0, (julianday(?) - julianday(m.started_at)) * 86400.0), "
    f"{_VALUE_PLACEHOLDERS} "
    "FROM missions m WHERE m.id = ? AND m.ended_at IS NULL"
)


class MissionNotFoundError(LookupError):
    """La misión pedida no existe."""


class MissionStateError(RuntimeError):
    """Operación no válida para el estado actual (p. ej. ya hay una activa)."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _elapsed_s(start_iso: str, moment_iso: str) -> float:
    delta = datetime.fromisoformat(moment_iso) - datetime.fromisoformat(start_iso)
    return round(max(0.0, delta.total_seconds()), 3)


def _round(value: float | None) -> float | None:
    return None if value is None else round(value, 2)


def _normalize_legacy_rows(conn: sqlite3.Connection) -> None:
    """
    Recalcula `sequence` (1..N por misión) y `mission_time_s` (segundos desde
    el inicio de la misión) para datos guardados antes de DATA_VERSION 1.
    Es determinista: el resultado depende solo de `started_at` y `received_at`.
    """
    missions = conn.execute("SELECT id, started_at FROM missions").fetchall()
    for mission in missions:
        rows = conn.execute(
            "SELECT id, received_at FROM telemetry WHERE mission_id = ? ORDER BY id",
            (mission["id"],),
        ).fetchall()
        updates = [
            (sequence, _elapsed_s(mission["started_at"], row["received_at"]), row["id"])
            for sequence, row in enumerate(rows, start=1)
        ]
        conn.executemany(
            "UPDATE telemetry SET sequence = ?, mission_time_s = ? WHERE id = ?",
            updates,
        )


class Database:
    def __init__(self, path: str | Path = DEFAULT_DB_PATH):
        self._path = str(path)
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            # WAL: permite exportar/consultar mientras se sigue escribiendo.
            conn.execute("PRAGMA journal_mode = WAL")
            conn.executescript(SCHEMA)
        self._upgrade_data()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self._path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _upgrade_data(self) -> None:
        with self._connect() as conn:
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            if version >= DATA_VERSION:
                return
            _normalize_legacy_rows(conn)
            conn.execute(f"PRAGMA user_version = {DATA_VERSION}")

    # ------------------------------------------------------------------
    # Misiones
    # ------------------------------------------------------------------

    def create_mission(self, name: str, notes: str | None = None) -> dict:
        try:
            with self._connect() as conn:
                cur = conn.execute(
                    "INSERT INTO missions (name, notes, started_at) VALUES (?, ?, ?)",
                    (name, notes, _now()),
                )
                mission_id = cur.lastrowid
        except sqlite3.IntegrityError as exc:
            # Único índice único de la tabla: idx_one_active_mission.
            raise MissionStateError(
                "Ya hay una misión activa; finalízala antes de iniciar otra."
            ) from exc
        return self.get_mission(mission_id)

    def end_mission(self, mission_id: int) -> dict:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT ended_at FROM missions WHERE id = ?", (mission_id,)
            ).fetchone()
            if row is None:
                raise MissionNotFoundError(f"No existe la misión {mission_id}.")
            if row["ended_at"] is not None:
                raise MissionStateError("La misión ya estaba finalizada.")
            conn.execute(
                "UPDATE missions SET ended_at = ? WHERE id = ?", (_now(), mission_id)
            )
        return self.get_mission(mission_id)

    def get_mission(self, mission_id: int) -> dict:
        with self._connect() as conn:
            row = conn.execute(
                _MISSION_SELECT + " WHERE m.id = ?", (mission_id,)
            ).fetchone()
        if row is None:
            raise MissionNotFoundError(f"No existe la misión {mission_id}.")
        return dict(row)

    def list_missions(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(_MISSION_SELECT + " ORDER BY m.id DESC").fetchall()
        return [dict(r) for r in rows]

    def close_orphan_missions(self) -> int:
        """
        Cierra misiones que quedaron activas por un apagado inesperado del
        backend. `ended_at` = última lectura guardada (o el inicio si no hubo).
        No se reanudan: al reiniciar, la fuente de datos también empieza de cero.
        """
        with self._connect() as conn:
            cur = conn.execute(
                """
                UPDATE missions
                SET ended_at = COALESCE(
                    (SELECT MAX(received_at) FROM telemetry
                     WHERE mission_id = missions.id),
                    started_at)
                WHERE ended_at IS NULL
                """
            )
            return cur.rowcount

    # ------------------------------------------------------------------
    # Telemetría
    # ------------------------------------------------------------------

    def insert_telemetry(self, mission_id: int, record: dict) -> bool:
        """
        Guarda una lectura procesada. Devuelve False (sin insertar) si la
        misión ya no está activa. `sequence` y `mission_time_s` del registro
        se ignoran: se calculan aquí, relativos a la misión.
        """
        values = (
            record["received_at"],
            *(record[name] for name in TELEMETRY_FIELDS),
            1 if record["valid"] else 0,
            json.dumps(record["warnings"], ensure_ascii=False),
        )
        with self._connect() as conn:
            cur = conn.execute(
                _INSERT_TELEMETRY_SQL,
                (record["received_at"], *values, mission_id),
            )
            return cur.rowcount == 1

    def fetch_telemetry_batch(
        self, mission_id: int, after_id: int = 0, limit: int = 1000
    ) -> list[dict]:
        """
        Siguiente bloque de lecturas de una misión (paginación por id).
        Permite exportar misiones grandes sin cargarlas completas en memoria.
        """
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM telemetry WHERE mission_id = ? AND id > ? "
                "ORDER BY id LIMIT ?",
                (mission_id, after_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Análisis histórico (Prototipo 1)
    # ------------------------------------------------------------------

    def mission_stats(self, mission_id: int) -> dict:
        """Estadísticas básicas de una misión: duración, conteos y mín./prom./máx."""
        self.get_mission(mission_id)  # MissionNotFoundError si no existe
        aggregates = ", ".join(
            f"MIN({f}) AS {f}_min, AVG({f}) AS {f}_avg, MAX({f}) AS {f}_max"
            for f in TELEMETRY_FIELDS
        )
        query = (
            "SELECT COUNT(*) AS samples, "
            "COALESCE(SUM(CASE WHEN valid = 0 THEN 1 ELSE 0 END), 0) AS invalid_samples, "
            "MAX(mission_time_s) AS duration_s, "
            f"{aggregates} FROM telemetry WHERE mission_id = ?"
        )
        with self._connect() as conn:
            row = conn.execute(query, (mission_id,)).fetchone()
        return {
            "mission_id": mission_id,
            "samples": row["samples"],
            "invalid_samples": row["invalid_samples"],
            "duration_s": row["duration_s"],
            "fields": {
                f: {
                    "min": row[f"{f}_min"],
                    "avg": _round(row[f"{f}_avg"]),
                    "max": row[f"{f}_max"],
                }
                for f in TELEMETRY_FIELDS
            },
        }

    def fetch_series(self, mission_id: int, max_points: int) -> dict:
        """
        Serie para gráficas: como mucho ~max_points filas, tomadas a intervalos
        regulares (1 de cada `step`). Devuelve también el total real para que la
        interfaz indique que hubo muestreo.
        """
        self.get_mission(mission_id)  # MissionNotFoundError si no existe
        columns = ", ".join(SERIES_COLUMNS)
        with self._connect() as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM telemetry WHERE mission_id = ?", (mission_id,)
            ).fetchone()[0]
            step = max(1, math.ceil(total / max_points))
            rows = conn.execute(
                f"WITH numbered AS ("
                f"  SELECT {columns}, ROW_NUMBER() OVER (ORDER BY id) AS rn"
                "  FROM telemetry WHERE mission_id = ?"
                ") "
                f"SELECT {columns} FROM numbered WHERE (rn - 1) % ? = 0 ORDER BY rn",
                (mission_id, step),
            ).fetchall()
        return {"total": total, "step": step, "points": [dict(r) for r in rows]}
