"""Pruebas de alertas y diagnóstico (Prototipo 2), sin depender de hardware."""

import asyncio
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.alerts import (  # noqa: E402
    CRITICAL,
    FRAME_ERRORS,
    INVALID_DATA,
    LINK_LOST,
    LOW_SNR,
    SERIAL_UNAVAILABLE,
    WARNING,
    WEAK_RSSI,
    AlertConfig,
    AlertEngine,
)
from app.telemetry.processor import process  # noqa: E402
from app.telemetry.schema import TelemetryReading  # noqa: E402
from app.telemetry.serial_esp32 import SerialESP32  # noqa: E402

VALID_LINE = "571617,22.5,410,101.3,150.0,9.8,1.2,-80,5.5\n"


def reading(**overrides) -> dict:
    record = {
        "rssi_dbm": -80.0,
        "snr_db": 6.0,
        "valid": True,
        "warnings": [],
    }
    record.update(overrides)
    return record


class FakeClock:
    """Reloj de pared determinista para las marcas de tiempo de los eventos."""

    def __init__(self):
        self.n = 0

    def __call__(self) -> str:
        self.n += 1
        return f"t{self.n:04d}"


def make_engine(**config) -> AlertEngine:
    return AlertEngine(AlertConfig(**config), wall_clock=FakeClock())


def active_codes(engine: AlertEngine) -> dict:
    return {a["code"]: a["severity"] for a in engine.snapshot(0.0)["active"]}


class ConfigTests(unittest.TestCase):
    def test_defaults_are_valid(self):
        config = AlertConfig()
        self.assertGreater(config.rssi_warn_dbm, config.rssi_crit_dbm)

    def test_from_env_overrides_only_given_values(self):
        config = AlertConfig.from_env(
            {"ALERT_LINK_TIMEOUT_S": "12", "ALERT_DISCARD_COUNT": "5"}
        )
        self.assertEqual(config.link_timeout_s, 12.0)
        self.assertEqual(config.discard_count, 5)
        self.assertEqual(config.rssi_warn_dbm, AlertConfig().rssi_warn_dbm)

    def test_from_env_ignores_empty_values(self):
        config = AlertConfig.from_env({"ALERT_LINK_TIMEOUT_S": "  "})
        self.assertEqual(config.link_timeout_s, AlertConfig().link_timeout_s)

    def test_from_env_rejects_non_numeric(self):
        with self.assertRaises(ValueError) as ctx:
            AlertConfig.from_env({"ALERT_RSSI_WARN_DBM": "fuerte"})
        self.assertIn("ALERT_RSSI_WARN_DBM", str(ctx.exception))

    def test_rssi_thresholds_must_be_ordered(self):
        with self.assertRaises(ValueError):
            AlertConfig(rssi_warn_dbm=-110.0, rssi_crit_dbm=-100.0)

    def test_invalid_values_are_rejected(self):
        for bad in (
            {"link_timeout_s": 0},
            {"link_timeout_s": float("nan")},
            {"hysteresis_db": -1},
            {"invalid_consecutive": 0},
            {"discard_window_s": 0},
            {"discard_count": 0},
        ):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                AlertConfig(**bad)


class SignalTests(unittest.TestCase):
    def test_nominal_reading_raises_nothing(self):
        engine = make_engine()
        engine.on_reading(reading(), now=0.0)
        self.assertEqual(active_codes(engine), {})
        self.assertEqual(engine.link_state(), "ok")

    def test_rssi_warning_then_critical(self):
        engine = make_engine()
        engine.on_reading(reading(rssi_dbm=-101.0), now=0.0)
        self.assertEqual(active_codes(engine), {WEAK_RSSI: WARNING})
        engine.on_reading(reading(rssi_dbm=-112.0), now=1.0)
        self.assertEqual(active_codes(engine), {WEAK_RSSI: CRITICAL})

    def test_rssi_exactly_on_threshold_alerts(self):
        engine = make_engine()
        engine.on_reading(reading(rssi_dbm=-100.0), now=0.0)
        self.assertEqual(active_codes(engine), {WEAK_RSSI: WARNING})

    def test_hysteresis_prevents_flapping(self):
        engine = make_engine()  # aviso en -100, histéresis 3 dB
        engine.on_reading(reading(rssi_dbm=-101.0), now=0.0)
        events_before = len(engine.snapshot(0.0)["events"])
        # Oscila alrededor del umbral sin superar el margen: sigue activa, sin eventos nuevos.
        for i, rssi in enumerate((-99.0, -101.0, -98.5, -100.5), start=1):
            engine.on_reading(reading(rssi_dbm=rssi), now=float(i))
        self.assertEqual(active_codes(engine), {WEAK_RSSI: WARNING})
        self.assertEqual(len(engine.snapshot(0.0)["events"]), events_before)
        # Supera el margen (-100 + 3 = -97): se resuelve.
        engine.on_reading(reading(rssi_dbm=-96.0), now=10.0)
        self.assertEqual(active_codes(engine), {})

    def test_critical_steps_down_to_warning_before_clearing(self):
        engine = make_engine()
        engine.on_reading(reading(rssi_dbm=-115.0), now=0.0)
        self.assertEqual(active_codes(engine), {WEAK_RSSI: CRITICAL})
        engine.on_reading(reading(rssi_dbm=-105.0), now=1.0)  # > -110 + 3
        self.assertEqual(active_codes(engine), {WEAK_RSSI: WARNING})
        engine.on_reading(reading(rssi_dbm=-90.0), now=2.0)
        self.assertEqual(active_codes(engine), {})

    def test_low_snr_with_hysteresis(self):
        engine = make_engine()
        engine.on_reading(reading(snr_db=-1.0), now=0.0)
        self.assertEqual(active_codes(engine), {LOW_SNR: WARNING})
        engine.on_reading(reading(snr_db=2.0), now=1.0)  # dentro del margen (0 + 3)
        self.assertEqual(active_codes(engine), {LOW_SNR: WARNING})
        engine.on_reading(reading(snr_db=4.0), now=2.0)
        self.assertEqual(active_codes(engine), {})

    def test_custom_thresholds_are_used(self):
        engine = make_engine(rssi_warn_dbm=-80.0, rssi_crit_dbm=-90.0)
        engine.on_reading(reading(rssi_dbm=-85.0), now=0.0)
        self.assertEqual(active_codes(engine), {WEAK_RSSI: WARNING})


class LinkTests(unittest.TestCase):
    def test_waiting_before_first_frame_is_not_an_alert(self):
        engine = make_engine(link_timeout_s=5.0)
        engine.tick(now=100.0, source_connected=True)
        self.assertEqual(engine.link_state(), "waiting")
        self.assertEqual(active_codes(engine), {})
        self.assertIsNone(engine.snapshot(100.0)["seconds_since_last_frame"])

    def test_link_lost_after_timeout_and_recovers(self):
        engine = make_engine(link_timeout_s=5.0)
        engine.on_reading(reading(), now=10.0)
        engine.tick(now=14.9, source_connected=True)
        self.assertEqual(engine.link_state(), "ok")
        engine.tick(now=15.1, source_connected=True)
        self.assertEqual(active_codes(engine), {LINK_LOST: CRITICAL})
        self.assertEqual(engine.link_state(), "lost")
        engine.on_reading(reading(), now=20.0)
        self.assertEqual(active_codes(engine), {})
        self.assertEqual(engine.link_state(), "ok")

    def test_link_lost_clears_stale_signal_alerts(self):
        engine = make_engine(link_timeout_s=5.0)
        engine.on_reading(reading(rssi_dbm=-112.0, snr_db=-5.0), now=0.0)
        self.assertEqual(active_codes(engine), {WEAK_RSSI: CRITICAL, LOW_SNR: WARNING})
        engine.tick(now=6.0, source_connected=True)
        self.assertEqual(active_codes(engine), {LINK_LOST: CRITICAL})

    def test_link_lost_is_raised_only_once(self):
        engine = make_engine(link_timeout_s=5.0)
        engine.on_reading(reading(), now=0.0)
        for t in (6.0, 7.0, 8.0):
            engine.tick(now=t, source_connected=True)
        raised = [e for e in engine.snapshot(8.0)["events"] if e["code"] == LINK_LOST]
        self.assertEqual(len(raised), 1)

    def test_seconds_since_last_frame(self):
        engine = make_engine()
        engine.on_reading(reading(), now=10.0)
        self.assertEqual(engine.snapshot(12.34)["seconds_since_last_frame"], 2.3)


class InvalidDataTests(unittest.TestCase):
    def test_alert_after_consecutive_invalid_readings(self):
        engine = make_engine(invalid_consecutive=3)
        bad = reading(valid=False, warnings=["altitude_m=3500 fuera de rango"])
        engine.on_reading(bad, now=0.0)
        engine.on_reading(bad, now=1.0)
        self.assertEqual(active_codes(engine), {})
        engine.on_reading(bad, now=2.0)
        self.assertEqual(active_codes(engine), {INVALID_DATA: WARNING})
        message = engine.snapshot(2.0)["active"][0]["message"]
        self.assertIn("altitude_m", message)

    def test_valid_reading_resets_the_streak_and_clears(self):
        engine = make_engine(invalid_consecutive=2)
        bad = reading(valid=False, warnings=["x"])
        engine.on_reading(bad, now=0.0)
        engine.on_reading(bad, now=1.0)
        self.assertEqual(active_codes(engine), {INVALID_DATA: WARNING})
        engine.on_reading(reading(), now=2.0)
        self.assertEqual(active_codes(engine), {})
        engine.on_reading(bad, now=3.0)  # la racha empieza de nuevo
        self.assertEqual(active_codes(engine), {})

    def test_processor_does_not_flag_weak_signal_as_invalid(self):
        weak = TelemetryReading(
            altitude_m=100.0,
            temperature_c=20.0,
            pressure_kpa=100.0,
            co2_ppm=400.0,
            velocity_ms=1.0,
            acceleration_ms2=9.8,
            rssi_dbm=-115.0,
            snr_db=-5.0,
            sequence=1,
            mission_time_s=1.0,
        )
        processed = process(weak)
        self.assertTrue(processed.valid)
        self.assertEqual(processed.warnings, [])


class SerialAlertTests(unittest.TestCase):
    def test_serial_unavailable_raises_and_clears(self):
        engine = make_engine()
        engine.tick(now=0.0, source_connected=False)
        self.assertEqual(active_codes(engine), {SERIAL_UNAVAILABLE: CRITICAL})
        engine.tick(now=1.0, source_connected=True)
        self.assertEqual(active_codes(engine), {})

    def test_frame_errors_alert_when_discards_accumulate(self):
        engine = make_engine(discard_window_s=10.0, discard_count=3)
        engine.tick(0.0, True, {"frames_discarded": 0})
        engine.tick(1.0, True, {"frames_discarded": 2})
        self.assertEqual(active_codes(engine), {})
        engine.tick(2.0, True, {"frames_discarded": 3})
        self.assertEqual(active_codes(engine), {FRAME_ERRORS: WARNING})

    def test_frame_errors_clear_when_window_passes_without_new_discards(self):
        engine = make_engine(discard_window_s=10.0, discard_count=2)
        engine.tick(0.0, True, {"frames_discarded": 2})
        self.assertEqual(active_codes(engine), {FRAME_ERRORS: WARNING})
        engine.tick(5.0, True, {"frames_discarded": 2})
        self.assertEqual(active_codes(engine), {FRAME_ERRORS: WARNING})
        engine.tick(10.5, True, {"frames_discarded": 2})
        self.assertEqual(active_codes(engine), {})

    def test_source_restart_resets_discard_baseline(self):
        engine = make_engine(discard_window_s=10.0, discard_count=2)
        engine.tick(0.0, True, {"frames_discarded": 7})
        engine.tick(20.0, True, {"frames_discarded": 7})  # ya fuera de la ventana
        engine.tick(21.0, True, {"frames_discarded": 0})  # reinicio de la fuente
        engine.tick(22.0, True, {"frames_discarded": 1})
        self.assertEqual(active_codes(engine), {})

    def test_source_without_diagnostics_is_supported(self):
        engine = make_engine()
        engine.tick(0.0, True, None)
        engine.tick(1.0, True, {})
        self.assertEqual(active_codes(engine), {})


class SnapshotTests(unittest.TestCase):
    def test_snapshot_shape_and_ordering(self):
        engine = make_engine(link_timeout_s=5.0)
        engine.on_reading(reading(rssi_dbm=-101.0), now=0.0)  # warning
        engine.tick(0.5, source_connected=False, diagnostics={"frames_ok": 4})  # critical
        snap = engine.snapshot(0.5)
        self.assertEqual(snap["type"], "alerts")
        self.assertEqual(
            set(snap),
            {"type", "link", "seconds_since_last_frame", "active", "events", "diagnostics"},
        )
        # Las críticas van primero.
        self.assertEqual([a["severity"] for a in snap["active"]], [CRITICAL, WARNING])
        self.assertEqual(snap["diagnostics"], {"frames_ok": 4})

    def test_events_are_newest_first_and_record_raise_and_clear(self):
        engine = make_engine()
        engine.on_reading(reading(rssi_dbm=-101.0), now=0.0)
        engine.on_reading(reading(rssi_dbm=-90.0), now=1.0)
        events = engine.snapshot(1.0)["events"]
        self.assertEqual([e["state"] for e in events], ["cleared", "raised"])
        self.assertTrue(all(e["code"] == WEAK_RSSI for e in events))

    def test_event_history_is_bounded(self):
        engine = make_engine()
        for i in range(100):
            engine.tick(float(i), source_connected=(i % 2 == 0))
        self.assertLessEqual(len(engine.snapshot(100.0)["events"]), 20)


class SerialDiagnosticsTests(unittest.IsolatedAsyncioTestCase):
    async def test_counters_track_ok_and_discarded_frames(self):
        source = SerialESP32(
            port="loop://", baudrate=9600, timeout_s=0.2, expected_pass="571617"
        )
        self.assertTrue(source._try_open())
        source._serial.write(b"too,few\n")
        source._serial.write(b"zzz,22.5,410,101.3,150.0,9.8,1.2,-80,5.5\n")
        source._serial.write(VALID_LINE.encode("utf-8"))
        await asyncio.wait_for(source.read(), timeout=2.0)
        diag = source.diagnostics()
        self.assertEqual(diag["frames_ok"], 1)
        self.assertEqual(diag["frames_discarded"], 2)
        self.assertEqual(diag["disconnects"], 0)
        self.assertIn("pass", diag["last_error"])
        self.assertEqual(diag["baudrate"], 9600)
        source.close()

    async def test_blank_lines_are_not_counted_as_discarded(self):
        source = SerialESP32(port="loop://", baudrate=9600, timeout_s=0.2)
        source._try_open()
        source._serial.write(b"\r\n\n")
        source._serial.write(VALID_LINE.encode("utf-8"))
        await asyncio.wait_for(source.read(), timeout=2.0)
        self.assertEqual(source.diagnostics()["frames_discarded"], 0)
        source.close()

    async def test_missing_port_records_error(self):
        source = SerialESP32(
            port="COM_DOES_NOT_EXIST_9", baudrate=9600, timeout_s=0.1
        )
        self.assertFalse(source._try_open())
        self.assertIn("no disponible", source.diagnostics()["last_error"])

    async def test_disconnect_is_counted(self):
        source = SerialESP32(port="loop://", baudrate=9600, timeout_s=0.2)
        source._try_open()
        source._mark_disconnected(OSError("cable retirado"))
        self.assertEqual(source.diagnostics()["disconnects"], 1)
        self.assertFalse(source.is_connected())


if __name__ == "__main__":
    unittest.main()
