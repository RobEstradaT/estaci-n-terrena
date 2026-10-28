"""Pruebas del análisis histórico: tiempo normalizado, migración, estadísticas y series."""

import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import DATA_VERSION, Database, MissionNotFoundError  # noqa: E402


def record_at(mission: dict, seconds: float, **overrides) -> dict:
    """Lectura recibida `seconds` después del inicio de la misión."""
    start = datetime.fromisoformat(mission["started_at"])
    record = {
        "altitude_m": 100.0,
        "temperature_c": 20.0,
        "pressure_kpa": 100.0,
        "co2_ppm": 400.0,
        "velocity_ms": 1.0,
        "acceleration_ms2": 9.8,
        "rssi_dbm": -80.0,
        "snr_db": 5.0,
        "sequence": 0,
        "mission_time_s": 0.0,
        "received_at": (start + timedelta(seconds=seconds)).isoformat(),
        "valid": True,
        "warnings": [],
    }
    record.update(overrides)
    return record


class HistoryTestCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.db_path = Path(tmp.name) / "history.db"
        self.db = Database(self.db_path)


class NormalizationTests(HistoryTestCase):
    def test_sequence_starts_at_one_for_each_mission(self):
        a = self.db.create_mission("A")
        self.db.insert_telemetry(a["id"], record_at(a, 1))
        self.db.insert_telemetry(a["id"], record_at(a, 2))
        self.db.end_mission(a["id"])

        b = self.db.create_mission("B")
        self.db.insert_telemetry(b["id"], record_at(b, 1))
        rows = self.db.fetch_telemetry_batch(b["id"])
        self.assertEqual(rows[0]["sequence"], 1)

    def test_mission_time_is_seconds_since_mission_start(self):
        mission = self.db.create_mission("A")
        self.db.insert_telemetry(mission["id"], record_at(mission, 5.0))
        self.db.insert_telemetry(mission["id"], record_at(mission, 7.25))
        rows = self.db.fetch_telemetry_batch(mission["id"])
        self.assertAlmostEqual(rows[0]["mission_time_s"], 5.0, delta=0.01)
        self.assertAlmostEqual(rows[1]["mission_time_s"], 7.25, delta=0.01)

    def test_mission_time_never_negative(self):
        mission = self.db.create_mission("A")
        # Lectura recibida justo antes de pulsar "Nueva misión" (carrera benigna).
        self.db.insert_telemetry(mission["id"], record_at(mission, -0.5))
        row = self.db.fetch_telemetry_batch(mission["id"])[0]
        self.assertEqual(row["mission_time_s"], 0.0)

    def test_source_values_are_not_kept(self):
        mission = self.db.create_mission("A")
        self.db.insert_telemetry(
            mission["id"], record_at(mission, 1, sequence=999, mission_time_s=500.0)
        )
        row = self.db.fetch_telemetry_batch(mission["id"])[0]
        self.assertEqual(row["sequence"], 1)
        self.assertAlmostEqual(row["mission_time_s"], 1.0, delta=0.01)

    def test_upgrade_normalizes_legacy_rows(self):
        mission = self.db.create_mission("Vieja")
        for second in (3, 4):
            self.db.insert_telemetry(mission["id"], record_at(mission, second))

        # Simula una base de la versión anterior: valores de la fuente y versión 0.
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("UPDATE telemetry SET sequence = 900 + id, mission_time_s = -1")
            conn.execute("PRAGMA user_version = 0")
            conn.commit()
        finally:
            conn.close()

        upgraded = Database(self.db_path)
        rows = upgraded.fetch_telemetry_batch(mission["id"])
        self.assertEqual([r["sequence"] for r in rows], [1, 2])
        self.assertAlmostEqual(rows[0]["mission_time_s"], 3.0, delta=0.01)
        self.assertAlmostEqual(rows[1]["mission_time_s"], 4.0, delta=0.01)

        conn = sqlite3.connect(self.db_path)
        try:
            version = conn.execute("PRAGMA user_version").fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(version, DATA_VERSION)


class StatsTests(HistoryTestCase):
    def test_empty_mission_has_no_values(self):
        mission = self.db.create_mission("Vacía")
        stats = self.db.mission_stats(mission["id"])
        self.assertEqual(stats["samples"], 0)
        self.assertEqual(stats["invalid_samples"], 0)
        self.assertIsNone(stats["duration_s"])
        self.assertIsNone(stats["fields"]["altitude_m"]["min"])
        self.assertIsNone(stats["fields"]["altitude_m"]["avg"])

    def test_stats_summarize_values_and_invalid_samples(self):
        mission = self.db.create_mission("A")
        self.db.insert_telemetry(mission["id"], record_at(mission, 1, altitude_m=100.0))
        self.db.insert_telemetry(mission["id"], record_at(mission, 2, altitude_m=200.0))
        self.db.insert_telemetry(
            mission["id"], record_at(mission, 3, altitude_m=300.0, valid=False)
        )
        stats = self.db.mission_stats(mission["id"])
        self.assertEqual(stats["samples"], 3)
        self.assertEqual(stats["invalid_samples"], 1)
        self.assertAlmostEqual(stats["duration_s"], 3.0, delta=0.01)
        altitude = stats["fields"]["altitude_m"]
        self.assertEqual(altitude["min"], 100.0)
        self.assertEqual(altitude["max"], 300.0)
        self.assertEqual(altitude["avg"], 200.0)

    def test_stats_unknown_mission(self):
        with self.assertRaises(MissionNotFoundError):
            self.db.mission_stats(999)


class SeriesTests(HistoryTestCase):
    def test_small_mission_returns_every_point(self):
        mission = self.db.create_mission("A")
        for second in range(1, 6):
            self.db.insert_telemetry(mission["id"], record_at(mission, second))
        series = self.db.fetch_series(mission["id"], max_points=10)
        self.assertEqual(series["total"], 5)
        self.assertEqual(series["step"], 1)
        self.assertEqual(len(series["points"]), 5)
        self.assertIn("altitude_m", series["points"][0])
        self.assertIn("mission_time_s", series["points"][0])

    def test_long_mission_is_downsampled(self):
        mission = self.db.create_mission("A")
        for second in range(1, 26):
            self.db.insert_telemetry(mission["id"], record_at(mission, second))
        series = self.db.fetch_series(mission["id"], max_points=10)
        self.assertEqual(series["total"], 25)
        self.assertEqual(series["step"], 3)
        self.assertEqual(len(series["points"]), 9)
        self.assertEqual(series["points"][0]["sequence"], 1)
        self.assertEqual(series["points"][-1]["sequence"], 25)

    def test_empty_mission_series(self):
        mission = self.db.create_mission("A")
        series = self.db.fetch_series(mission["id"], max_points=10)
        self.assertEqual(series["total"], 0)
        self.assertEqual(series["points"], [])

    def test_series_unknown_mission(self):
        with self.assertRaises(MissionNotFoundError):
            self.db.fetch_series(999, max_points=10)


if __name__ == "__main__":
    unittest.main()
