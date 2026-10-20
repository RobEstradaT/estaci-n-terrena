"""
Persistencia en SQLite (Incremento 6).

Responsabilidad: guardar misiones y lecturas de telemetría ya procesadas
(el `dict` que produce `ProcessedTelemetry.to_dict()`) y devolverlas cuando
se consulten. No conoce FastAPI, WebSocket ni la fuente de datos.

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
"""

from __future__ import annotations

import json
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
"""

_MISSION_SELECT = """
SELECT m.id, m.name, m.notes, m.started_at, m.ended_at,
       (SELECT COUNT(*) FROM telemetry t WHERE t.mission_id = m.id) AS sample_count
FROM missions m
"""


class MissionNotFoundError(LookupError):
    """La misión pedida no existe."""


class MissionStateError(RuntimeError):
    """Operación no válida para el estado actual (p. ej. ya hay una activa)."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    def __init__(self, path: str | Path = DEFAULT_DB_PATH):
        self._path = str(path)
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            # WAL: permite exportar/consultar mientras se sigue escribiendo.
            conn.execute("PRAGMA journal_mode = WAL")
            conn.executescript(SCHEMA)

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
        misión ya no está activa.
        """
        columns = (
            "sequence",
            "mission_time_s",
            "received_at",
            *TELEMETRY_FIELDS,
            "valid",
            "warnings",
        )
        values = (
            record["sequence"],
            record["mission_time_s"],
            record["received_at"],
            *(record[name] for name in TELEMETRY_FIELDS),
            1 if record["valid"] else 0,
            json.dumps(record["warnings"], ensure_ascii=False),
        )
        placeholders = ", ".join("?" for _ in columns)
        sql = (
            f"INSERT INTO telemetry (mission_id, {', '.join(columns)}) "
            f"SELECT ?, {placeholders} "
            "WHERE EXISTS (SELECT 1 FROM missions WHERE id = ? AND ended_at IS NULL)"
        )
        with self._connect() as conn:
            cur = conn.execute(sql, (mission_id, *values, mission_id))
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
