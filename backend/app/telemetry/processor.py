"""
Procesamiento y validación básica de telemetría (Incremento 1).

Responsabilidad: recibir una TelemetryReading ya estructurada (venga de
Simulator o, en el futuro, de SerialESP32) y determinar si sus valores
son plausibles, generando advertencias cuando no lo son. No descarta
datos: los marca, para que el frontend y el registro histórico decidan
qué hacer con ellos.

Los rangos usados aquí son límites de sanidad orientativos (para detectar
errores evidentes de lectura o transmisión), no especificaciones oficiales
de los sensores del CanSat.
"""

from dataclasses import dataclass
from .schema import TelemetryReading, ProcessedTelemetry

RANGES = {
    "altitude_m": (0.0, 3000.0),
    "temperature_c": (-40.0, 60.0),
    "pressure_kpa": (50.0, 110.0),
    "co2_ppm": (0.0, 5000.0),
    "velocity_ms": (-70.0, 70.0),
    "acceleration_ms2": (0.0, 60.0),
    "rssi_dbm": (-130.0, -20.0),
    "snr_db": (-20.0, 20.0),
}


def process(reading: TelemetryReading) -> ProcessedTelemetry:
    warnings: list[str] = []

    for field_name, (low, high) in RANGES.items():
        value = getattr(reading, field_name)
        if value < low or value > high:
            warnings.append(
                f"{field_name}={value} fuera de rango esperado [{low}, {high}]"
            )

    # Señal débil: advertencia específica y accionable (ver Incremento 8,
    # aquí solo se detecta el caso más básico como parte de "procesamiento").
    if reading.rssi_dbm <= -110.0:
        warnings.append("Señal RSSI muy débil, posible pérdida de enlace inminente")

    valid = len(warnings) == 0

    return ProcessedTelemetry(reading=reading, valid=valid, warnings=warnings)
