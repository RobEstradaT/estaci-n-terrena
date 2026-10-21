"""
Fuente de telemetría UART real (Incremento 5).

`parse_frame` traduce una línea ASCII del ESP32 a `TelemetryReading`.
`SerialESP32` solo abre el puerto, lee línea por línea y delega el
parseo; no conoce el orden de campos (ver ARCHITECTURE.md sección 3 y
PROTOCOL.md).
"""

from __future__ import annotations

import asyncio
import logging
import math
import time

import serial
from serial import SerialException

from .schema import TelemetryReading
from .source import TelemetrySource

logger = logging.getLogger(__name__)

# Confirmado en PROTOCOL.md: 9 campos separados por coma, terminados en \n.
EXPECTED_FIELD_COUNT = 9
FIELD_SEPARATOR = ","

# Índices confirmados: pass,value1..value6,rssi,snr
IDX_PASS = 0
IDX_TEMPERATURE = 1  # unidad pendiente de confirmar
IDX_CO2_PPM = 2
IDX_PRESSURE_KPA = 3
IDX_ALTITUDE_M = 4
IDX_ACCELERATION_MS2 = 5
IDX_VELOCITY_MS = 6
IDX_RSSI_DBM = 7
IDX_SNR_DB = 8


class InvalidFrameError(ValueError):
    """Trama rechazada: número de campos incorrecto o valor no numérico."""


def _parse_float(field: str, name: str) -> float:
    """
    Convierte un campo a float de forma defensiva.

    El tipo de dato y la precisión exactos siguen PENDIENTES DE CONFIRMAR
    en PROTOCOL.md; no se asume entero ni un número fijo de decimales.

    Se rechazan `nan` e `inf` (Arduino los imprime cuando falla un sensor):
    no son JSON válido y no se pueden guardar en la base de datos.
    """
    try:
        value = float(field)
    except (TypeError, ValueError) as exc:
        raise InvalidFrameError(
            f"campo '{name}' no numérico: {field!r}"
        ) from exc
    if not math.isfinite(value):
        raise InvalidFrameError(f"campo '{name}' no finito: {field!r}")
    return value


def parse_frame(
    raw_line: str,
    *,
    sequence: int = 0,
    mission_time_s: float = 0.0,
) -> TelemetryReading:
    """
    Traduce una línea cruda del ESP32 a TelemetryReading.

    Formato confirmado (PROTOCOL.md):
        pass,value1,value2,value3,value4,value5,value6,rssi,snr

    No valida `pass` (algoritmo PENDIENTE). No verifica checksum/CRC
    (no existen aún). Si el número de campos no es 9 o un valor de
    telemetría no convierte a un float finito, la trama se considera
    inválida (`InvalidFrameError`).
    """
    line = raw_line.strip()
    fields = line.split(FIELD_SEPARATOR)

    if len(fields) != EXPECTED_FIELD_COUNT:
        raise InvalidFrameError(
            f"se esperaban {EXPECTED_FIELD_COUNT} campos, se recibieron {len(fields)}"
        )

    # p0 (`pass`): presente; algoritmo/validación PENDIENTE DE CONFIRMAR.

    # unidad pendiente de confirmar
    temperature = _parse_float(fields[IDX_TEMPERATURE], "temperature")
    co2_ppm = _parse_float(fields[IDX_CO2_PPM], "co2_ppm")
    pressure_kpa = _parse_float(fields[IDX_PRESSURE_KPA], "pressure_kpa")
    altitude_m = _parse_float(fields[IDX_ALTITUDE_M], "altitude_m")
    acceleration_ms2 = _parse_float(fields[IDX_ACCELERATION_MS2], "acceleration_ms2")
    velocity_ms = _parse_float(fields[IDX_VELOCITY_MS], "velocity_ms")
    rssi_dbm = _parse_float(fields[IDX_RSSI_DBM], "rssi_dbm")
    snr_db = _parse_float(fields[IDX_SNR_DB], "snr_db")

    return TelemetryReading(
        altitude_m=altitude_m,
        temperature_c=temperature,
        pressure_kpa=pressure_kpa,
        co2_ppm=co2_ppm,
        velocity_ms=velocity_ms,
        acceleration_ms2=acceleration_ms2,
        rssi_dbm=rssi_dbm,
        snr_db=snr_db,
        sequence=sequence,
        mission_time_s=mission_time_s,
    )


def _open_port(port: str, baudrate: int, timeout_s: float) -> serial.Serial:
    """Abre un puerto real o una URL de pyserial (p. ej. loop:// para pruebas)."""
    if "://" in port:
        return serial.serial_for_url(port, baudrate=baudrate, timeout=timeout_s)
    return serial.Serial(port=port, baudrate=baudrate, timeout=timeout_s)


class SerialESP32(TelemetrySource):
    """
    Lee telemetría del ESP32 por UART (línea a línea) y la entrega
    como TelemetryReading, igual que Simulator.

    `poll_interval_s` queda en 0 (valor heredado): `read()` ya bloquea
    hasta recibir una trama, así que el ciclo del backend no debe añadir
    esperas que acumulen retraso.
    """

    def __init__(
        self,
        port: str,
        baudrate: int,
        timeout_s: float = 1.0,
        reconnect_delay_s: float = 1.0,
    ):
        if not port:
            raise ValueError("el puerto serial es obligatorio (no hardcodeado)")
        if not baudrate:
            raise ValueError("el baudrate es obligatorio (no hardcodeado)")

        self._port = port
        self._baudrate = baudrate
        self._timeout_s = timeout_s
        self._reconnect_delay_s = reconnect_delay_s
        self._serial: serial.Serial | None = None
        self._connected = False
        self._sequence = 0
        self._mission_t0: float | None = None

    def is_connected(self) -> bool:
        return self._connected and self._serial is not None and self._serial.is_open

    def close(self) -> None:
        if self._serial is not None:
            try:
                self._serial.close()
            except SerialException:
                logger.warning("error al cerrar el puerto serial %s", self._port)
            self._serial = None
        self._connected = False

    def _try_open(self) -> bool:
        if self._serial is not None and self._serial.is_open:
            self._connected = True
            return True
        try:
            self._serial = _open_port(self._port, self._baudrate, self._timeout_s)
            self._connected = True
            logger.info(
                "puerto serial abierto: %s @ %s baud",
                self._port,
                self._baudrate,
            )
            return True
        except (SerialException, OSError) as exc:
            self._connected = False
            self._serial = None
            logger.warning("puerto serial no disponible (%s): %s", self._port, exc)
            return False

    def _read_raw_line(self) -> str | None:
        """Lectura bloqueante de una línea. None = timeout sin datos."""
        if self._serial is None or not self._serial.is_open:
            raise SerialException("puerto cerrado")
        raw = self._serial.readline()
        if not raw:
            return None
        return raw.decode("utf-8", errors="replace")

    def _mark_disconnected(self, exc: Exception) -> None:
        self._connected = False
        logger.warning("desconexión serial (%s): %s", self._port, exc)
        try:
            if self._serial is not None:
                self._serial.close()
        except SerialException:
            pass
        self._serial = None

    async def read(self) -> TelemetryReading:
        """
        Espera una trama válida sin bloquear el event loop.

        `serial.Serial.readline()` y la apertura del puerto son I/O
        bloqueante de pyserial; ambas se ejecutan en un hilo del pool
        (`asyncio.to_thread`, equivalente a `loop.run_in_executor`).

        Puerto ausente, desconexión o línea corrupta se registran y no
        se propagan: se reintenta. Las tramas inválidas no incrementan
        la secuencia.
        """
        while True:
            opened = await asyncio.to_thread(self._try_open)
            if not opened:
                await asyncio.sleep(self._reconnect_delay_s)
                continue

            try:
                raw_line = await asyncio.to_thread(self._read_raw_line)
            except (SerialException, OSError) as exc:
                await asyncio.to_thread(self._mark_disconnected, exc)
                await asyncio.sleep(self._reconnect_delay_s)
                continue

            if raw_line is None:
                continue

            try:
                parsed = parse_frame(raw_line)
            except InvalidFrameError as exc:
                logger.warning("trama inválida descartada: %s | crudo=%r", exc, raw_line)
                continue

            self._sequence += 1
            if self._mission_t0 is None:
                self._mission_t0 = time.monotonic()
            parsed.sequence = self._sequence
            parsed.mission_time_s = round(time.monotonic() - self._mission_t0, 1)
            return parsed
