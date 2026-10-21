"""
Diagnóstico del puerto serial del ESP32, SIN levantar el backend.

Abre el puerto, lee tramas y muestra, para cada una, si `parse_frame` la
acepta y si `processor.process` la marca con advertencias. Sirve para
confirmar puerto, baudrate y formato antes de la prueba real.

Uso (desde la carpeta backend, con el venv activo):
    python tools/check_serial.py PUERTO BAUDRATE [--lines 20] [--idle-timeout 10]

Ejemplos:
    python tools/check_serial.py COM5 115200
    python tools/check_serial.py /dev/ttyUSB0 115200 --lines 50

Para listar los puertos disponibles:
    python -m serial.tools.list_ports -v
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import serial  # noqa: E402
from serial import SerialException  # noqa: E402

from app.telemetry.processor import process  # noqa: E402
from app.telemetry.serial_esp32 import InvalidFrameError, parse_frame  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnóstico del puerto serial del ESP32")
    parser.add_argument("port", help="p. ej. COM5 o /dev/ttyUSB0")
    parser.add_argument("baudrate", type=int, help="el mismo de Serial.begin(...) del ESP32")
    parser.add_argument("--lines", type=int, default=20, help="tramas a leer (default 20)")
    parser.add_argument(
        "--idle-timeout",
        type=float,
        default=10.0,
        help="segundos sin datos antes de rendirse (default 10)",
    )
    args = parser.parse_args()

    try:
        ser = serial.serial_for_url(args.port, baudrate=args.baudrate, timeout=1.0)
    except (SerialException, OSError) as exc:
        print(f"No se pudo abrir {args.port}: {exc}")
        print("  - ¿Es el puerto correcto? (python -m serial.tools.list_ports -v)")
        print("  - ¿Hay otro programa usándolo? (Monitor Serie del IDE, otro backend)")
        return 1

    print(f"Escuchando {args.port} @ {args.baudrate} baud (Ctrl+C para salir)...")
    print("Nota: la primera línea puede venir cortada; es normal.\n")

    ok = bad = garbled = 0
    last_data = time.monotonic()

    try:
        while ok + bad < args.lines:
            raw = ser.readline()
            if not raw:
                if time.monotonic() - last_data > args.idle_timeout:
                    print(f"Sin datos durante {args.idle_timeout:.0f} s. Me detengo.")
                    break
                continue

            last_data = time.monotonic()
            text = raw.decode("utf-8", errors="replace").rstrip("\r\n")

            try:
                reading = parse_frame(text)
            except InvalidFrameError as exc:
                bad += 1
                if "\ufffd" in text:
                    garbled += 1
                print(f"[FALLA] {text!r}")
                print(f"        motivo: {exc}")
                continue

            ok += 1
            print(f"[OK]    {text}")
            print(
                f"        temp={reading.temperature_c}  co2={reading.co2_ppm} ppm  "
                f"presión={reading.pressure_kpa} kPa  altura={reading.altitude_m} m"
            )
            print(
                f"        acel={reading.acceleration_ms2} m/s²  vel={reading.velocity_ms} m/s  "
                f"rssi={reading.rssi_dbm} dBm  snr={reading.snr_db} dB"
            )
            for warning in process(reading).warnings:
                print(f"        AVISO: {warning}")
    except KeyboardInterrupt:
        print("\nInterrumpido por el usuario.")
    finally:
        ser.close()

    print(f"\nResumen: {ok} válidas, {bad} con falla.")
    if ok == 0 and bad == 0:
        print("No llegó ninguna línea: revisa que el ESP32 esté transmitiendo, el cable USB")
        print("(que sea de datos), y que el receptor LoRa esté recibiendo del CanSat.")
    elif ok == 0 and garbled > 0:
        print("Caracteres ilegibles: el baudrate casi seguro no coincide con Serial.begin(...).")
    elif ok == 0:
        print("Llegan líneas pero ninguna coincide con el formato de 9 campos (ver PROTOCOL.md).")
    elif bad > 0:
        print("Algunas fallas al inicio son normales (arranque del ESP32 o línea cortada).")
    return 0 if ok > 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
