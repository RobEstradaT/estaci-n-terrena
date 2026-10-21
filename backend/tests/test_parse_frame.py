"""Pruebas del parser UART (Incremento 5), sin depender de hardware."""

import asyncio
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.telemetry.serial_esp32 import (  # noqa: E402
    InvalidFrameError,
    SerialESP32,
    parse_frame,
)

VALID = "abc123,22.5,410,101.3,150.0,9.8,1.2,-80,5.5\n"


class ParseFrameTests(unittest.TestCase):
    def test_valid_frame_maps_confirmed_order(self):
        reading = parse_frame(VALID)
        self.assertEqual(reading.temperature_c, 22.5)
        self.assertEqual(reading.co2_ppm, 410.0)
        self.assertEqual(reading.pressure_kpa, 101.3)
        self.assertEqual(reading.altitude_m, 150.0)
        self.assertEqual(reading.acceleration_ms2, 9.8)
        self.assertEqual(reading.velocity_ms, 1.2)
        self.assertEqual(reading.rssi_dbm, -80.0)
        self.assertEqual(reading.snr_db, 5.5)

    def test_pass_is_not_validated(self):
        # Cualquier texto en p0 es aceptable; no hay algoritmo confirmado.
        reading = parse_frame("not-a-known-algo,1,2,3,4,5,6,-70,1")
        self.assertEqual(reading.altitude_m, 4.0)

    def test_too_few_fields_is_invalid(self):
        with self.assertRaises(InvalidFrameError):
            parse_frame("1,2,3,4,5")

    def test_too_many_fields_is_invalid(self):
        with self.assertRaises(InvalidFrameError):
            parse_frame("1,2,3,4,5,6,7,8,9,10")

    def test_non_numeric_value_is_invalid(self):
        with self.assertRaises(InvalidFrameError):
            parse_frame("p,22.5,abc,101.3,150,9.8,1.2,-80,5.5")

    def test_nan_and_inf_are_invalid(self):
        # Arduino imprime nan/inf cuando falla un sensor.
        for bad in ("nan", "inf", "-inf"):
            with self.assertRaises(InvalidFrameError):
                parse_frame(f"p,22.5,{bad},101.3,150,9.8,1.2,-80,5.5")

    def test_empty_line_is_invalid(self):
        with self.assertRaises(InvalidFrameError):
            parse_frame("\n")


class SerialESP32LoopTests(unittest.IsolatedAsyncioTestCase):
    async def test_read_valid_line_from_loop_url(self):
        source = SerialESP32(port="loop://", baudrate=9600, timeout_s=0.5)
        self.assertTrue(source._try_open())
        self.assertTrue(source.is_connected())
        source._serial.write(VALID.encode("utf-8"))
        reading = await asyncio.wait_for(source.read(), timeout=2.0)
        self.assertEqual(reading.co2_ppm, 410.0)
        self.assertEqual(reading.sequence, 1)
        source.close()
        self.assertFalse(source.is_connected())

    async def test_corrupt_then_valid_does_not_crash(self):
        source = SerialESP32(port="loop://", baudrate=9600, timeout_s=0.2)
        source._try_open()
        source._serial.write(b"too,few\n")
        source._serial.write(VALID.encode("utf-8"))
        reading = await asyncio.wait_for(source.read(), timeout=2.0)
        self.assertEqual(reading.velocity_ms, 1.2)
        source.close()

    async def test_missing_port_stays_disconnected(self):
        source = SerialESP32(
            port="COM_DOES_NOT_EXIST_9",
            baudrate=9600,
            timeout_s=0.1,
            reconnect_delay_s=0.05,
        )
        self.assertFalse(source._try_open())
        self.assertFalse(source.is_connected())

    def test_serial_source_does_not_add_polling_delay(self):
        source = SerialESP32(port="loop://", baudrate=9600)
        self.assertEqual(source.poll_interval_s, 0.0)


if __name__ == "__main__":
    unittest.main()
