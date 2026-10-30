"""Pruebas de persistencia SQLite y exportación CSV y JSON (Incremento 6)."""

import csv
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import (  # noqa: E402
    Database,
    MissionNotFoundError,
    MissionStateError,
)
from app.exporter import CSV_COLUMNS, csv_chunks, export_filename, json_chunks  # noqa: E402


def make_record(sequence: int = 1, **overrides) -> dict:
    record = {
        "altitude_m": 100.0 + sequence,
        "temperature_c": 21.5,
        "pressure_kpa": 100.1,
        "co2_ppm": 415.0,
        "velocity_ms": 12.3,
        "acceleration_ms2": 9.9,
        "rssi_dbm": -80.0,
        "snr_db": 7.5,
        "sequence": sequence,
        "mission_time_s": float(sequence),
        "received_at": f"2026-10-19T12:00:{sequence:02d}+00:00",
        "valid": True,
        "warnings": [],
    }
    record.update(overrides)
    return record


class DatabaseTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.db_path = Path(self._tmp.name) / "test.db"
        self.db = Database(self.db_path)


class MissionTests(DatabaseTestCase):
    def test_create_mission_starts_active_and_empty(self):
        mission = self.db.create_mission("Prueba 1", "nota")
        self.assertEqual(mission["name"], "Prueba 1")
        self.assertEqual(mission["notes"], "nota")
        self.assertIsNone(mission["ended_at"])
        self.assertEqual(mission["sample_count"], 0)

    def test_only_one_active_mission_at_a_time(self):
        self.db.create_mission("A")
        with self.assertRaises(MissionStateError):
            self.db.create_mission("B")

    def test_can_create_new_mission_after_ending_previous(self):
        first = self.db.create_mission("A")
        self.db.end_mission(first["id"])
        second = self.db.create_mission("B")
        self.assertNotEqual(first["id"], second["id"])

    def test_end_mission_sets_ended_at(self):
        mission = self.db.create_mission("A")
        ended = self.db.end_mission(mission["id"])
        self.assertIsNotNone(ended["ended_at"])

    def test_end_unknown_mission(self):
        with self.assertRaises(MissionNotFoundError):
            self.db.end_mission(999)

    def test_end_already_ended_mission(self):
        mission = self.db.create_mission("A")
        self.db.end_mission(mission["id"])
        with self.assertRaises(MissionStateError):
            self.db.end_mission(mission["id"])

    def test_get_unknown_mission(self):
        with self.assertRaises(MissionNotFoundError):
            self.db.get_mission(999)

    def test_list_missions_newest_first_with_counts(self):
        a = self.db.create_mission("A")
        self.db.insert_telemetry(a["id"], make_record(1))
        self.db.insert_telemetry(a["id"], make_record(2))
        self.db.end_mission(a["id"])
        b = self.db.create_mission("B")
        missions = self.db.list_missions()
        self.assertEqual([m["id"] for m in missions], [b["id"], a["id"]])
        self.assertEqual(missions[0]["sample_count"], 0)
        self.assertEqual(missions[1]["sample_count"], 2)

    def test_orphan_active_mission_is_closed_on_restart(self):
        mission = self.db.create_mission("A")
        self.db.insert_telemetry(mission["id"], make_record(1))
        self.db.insert_telemetry(mission["id"], make_record(5))
        # Simula reinicio: nueva instancia sobre el mismo archivo.
        restarted = Database(self.db_path)
        self.assertEqual(restarted.close_orphan_missions(), 1)
        closed = restarted.get_mission(mission["id"])
        self.assertEqual(closed["ended_at"], "2026-10-19T12:00:05+00:00")
        self.assertEqual(restarted.close_orphan_missions(), 0)

    def test_orphan_mission_without_samples_uses_start_time(self):
        mission = self.db.create_mission("A")
        self.assertEqual(self.db.close_orphan_missions(), 1)
        closed = self.db.get_mission(mission["id"])
        self.assertEqual(closed["ended_at"], mission["started_at"])


class TelemetryTests(DatabaseTestCase):
    def test_insert_and_fetch_roundtrip(self):
        mission = self.db.create_mission("A")
        record = make_record(1, valid=False, warnings=["fuera de rango [0.0, 10.0]"])
        self.assertTrue(self.db.insert_telemetry(mission["id"], record))
        rows = self.db.fetch_telemetry_batch(mission["id"])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["altitude_m"], 101.0)
        self.assertEqual(rows[0]["valid"], 0)
        self.assertIn("fuera de rango", rows[0]["warnings"])

    def test_insert_rejected_when_mission_ended(self):
        mission = self.db.create_mission("A")
        self.db.end_mission(mission["id"])
        self.assertFalse(self.db.insert_telemetry(mission["id"], make_record(1)))
        self.assertEqual(self.db.fetch_telemetry_batch(mission["id"]), [])

    def test_insert_rejected_for_unknown_mission(self):
        self.assertFalse(self.db.insert_telemetry(42, make_record(1)))

    def test_missions_do_not_mix_data(self):
        a = self.db.create_mission("A")
        self.db.insert_telemetry(a["id"], make_record(1))
        self.db.end_mission(a["id"])
        b = self.db.create_mission("B")
        self.db.insert_telemetry(b["id"], make_record(2))
        self.db.insert_telemetry(b["id"], make_record(3))
        self.assertEqual(len(self.db.fetch_telemetry_batch(a["id"])), 1)
        self.assertEqual(len(self.db.fetch_telemetry_batch(b["id"])), 2)

    def test_fetch_batch_paginates_by_id(self):
        mission = self.db.create_mission("A")
        for i in range(1, 6):
            self.db.insert_telemetry(mission["id"], make_record(i))
        first = self.db.fetch_telemetry_batch(mission["id"], 0, 2)
        second = self.db.fetch_telemetry_batch(mission["id"], first[-1]["id"], 2)
        self.assertEqual([r["sequence"] for r in first], [1, 2])
        self.assertEqual([r["sequence"] for r in second], [3, 4])

    def test_data_persists_across_instances(self):
        mission = self.db.create_mission("A")
        self.db.insert_telemetry(mission["id"], make_record(1))
        reopened = Database(self.db_path)
        self.assertEqual(reopened.get_mission(mission["id"])["sample_count"], 1)


class ExportTests(DatabaseTestCase):
    def _export(self, mission_id: int, batch_size: int = 1000) -> str:
        return "".join(csv_chunks(self.db, mission_id, batch_size))

    def test_csv_has_bom_header_and_rows(self):
        mission = self.db.create_mission("A")
        for i in range(1, 4):
            self.db.insert_telemetry(mission["id"], make_record(i))
        text = self._export(mission["id"])
        self.assertTrue(text.startswith("\ufeff"))
        rows = list(csv.reader(io.StringIO(text.lstrip("\ufeff"))))
        self.assertEqual(tuple(rows[0]), CSV_COLUMNS)
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[1][rows[0].index("sequence")], "1")
        self.assertEqual(rows[1][rows[0].index("valid")], "1")

    def test_csv_of_empty_mission_has_only_header(self):
        mission = self.db.create_mission("A")
        rows = list(csv.reader(io.StringIO(self._export(mission["id"]).lstrip("\ufeff"))))
        self.assertEqual(len(rows), 1)

    def test_csv_spans_multiple_batches_without_losing_rows(self):
        mission = self.db.create_mission("A")
        for i in range(1, 8):
            self.db.insert_telemetry(mission["id"], make_record(i))
        rows = list(
            csv.reader(io.StringIO(self._export(mission["id"], batch_size=2).lstrip("\ufeff")))
        )
        self.assertEqual([r[0] for r in rows[1:]], [str(i) for i in range(1, 8)])

    def test_warnings_with_commas_and_accents_survive_roundtrip(self):
        mission = self.db.create_mission("A")
        warnings = [
            "altitude_m=3500 fuera de rango esperado [0.0, 3000.0]",
            "Señal RSSI muy débil, posible pérdida de enlace inminente",
        ]
        self.db.insert_telemetry(
            mission["id"], make_record(1, valid=False, warnings=warnings)
        )
        rows = list(csv.reader(io.StringIO(self._export(mission["id"]).lstrip("\ufeff"))))
        cell = rows[1][rows[0].index("warnings")]
        self.assertEqual(cell.split(" | "), warnings)
        self.assertEqual(rows[1][rows[0].index("valid")], "0")

    def test_export_filename_is_safe_ascii(self):
        self.assertEqual(
            export_filename({"id": 3, "name": "Lanzamiento Pachuca ¡Súper!"}),
            "mision_3_lanzamiento-pachuca-super.csv",
        )
        self.assertEqual(export_filename({"id": 7, "name": "???"}), "mision_7.csv")
        self.assertEqual(
            export_filename({"id": 1, "name": 'a/b\\c"d'}), "mision_1_a-b-c-d.csv"
        )


class JsonExportTests(DatabaseTestCase):
    def _export(self, mission_id: int, batch_size: int = 1000) -> dict:
        mission = self.db.get_mission(mission_id)
        return json.loads("".join(json_chunks(self.db, mission, batch_size)))

    def test_json_contains_mission_and_typed_telemetry(self):
        mission = self.db.create_mission("A")
        warnings = ["altitude_m=3500 fuera de rango esperado [0.0, 3000.0]"]
        self.db.insert_telemetry(mission["id"], make_record(1))
        self.db.insert_telemetry(
            mission["id"], make_record(2, valid=False, warnings=warnings)
        )
        doc = self._export(mission["id"])
        self.assertEqual(doc["mission"]["name"], "A")
        self.assertEqual(doc["mission"]["sample_count"], 2)
        self.assertEqual([r["sequence"] for r in doc["telemetry"]], [1, 2])
        self.assertEqual(doc["telemetry"][0]["altitude_m"], 101.0)
        self.assertIs(doc["telemetry"][0]["valid"], True)
        self.assertIs(doc["telemetry"][1]["valid"], False)
        self.assertEqual(doc["telemetry"][1]["warnings"], warnings)

    def test_json_spans_batches_without_losing_or_duplicating_rows(self):
        mission = self.db.create_mission("A")
        for i in range(1, 8):
            self.db.insert_telemetry(mission["id"], make_record(i))
        doc = self._export(mission["id"], batch_size=3)
        self.assertEqual([r["sequence"] for r in doc["telemetry"]], list(range(1, 8)))

    def test_empty_mission_gives_empty_telemetry_list(self):
        mission = self.db.create_mission("A")
        doc = self._export(mission["id"])
        self.assertEqual(doc["telemetry"], [])
        self.assertEqual(doc["mission"]["id"], mission["id"])

    def test_json_filename_uses_json_extension(self):
        self.assertEqual(
            export_filename({"id": 3, "name": "Prueba"}, "json"),
            "mision_3_prueba.json",
        )


if __name__ == "__main__":
    unittest.main()
