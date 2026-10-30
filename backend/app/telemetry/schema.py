"""
Modelo de datos de telemetría procesada.

IMPORTANTE (ver PROTOCOL.md):
El protocolo real de la ESP32 ya se confirmó parcialmente: el orden de
campos, el separador (coma), el terminador (`\\n`) y las unidades de todas
las variables, incluida la temperatura en °C, están CONFIRMADAS. Siguen
PENDIENTES DE CONFIRMAR el algoritmo de `pass` y el tipo de dato/
precisión de cada campo (además de checksum/CRC, que no existen en el
protocolo conocido).

Este esquema define la estructura INTERNA que usa el backend una vez que
un `TelemetrySource` (simulado o real) ya entregó los valores; no
representa la trama cruda del hardware. Los campos y unidades aquí ya
coinciden con los confirmados en PROTOCOL.md (incluida `pressure_kpa` en
kPa y la variable `acceleration_ms2`, que no estaba contemplada antes de
confirmar el protocolo), para que el Incremento 5 (`SerialESP32`) solo
tenga que parsear texto a estos mismos campos, sin conversión de unidades.

Cuando en el Incremento 5 se implemente `SerialESP32`, su responsabilidad
será traducir la trama real (`pass,value1,...,value6,rssi,snr`) a esta
misma estructura, de modo que el resto del sistema (procesamiento,
WebSocket, frontend) no tenga que cambiar.
"""

from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone


@dataclass
class TelemetryReading:
    """Una lectura de telemetría ya estructurada (no cruda)."""

    # Variables de telemetría (ver PROJECT_CONTEXT.md sección 5 / PROTOCOL.md)
    altitude_m: float
    temperature_c: float
    pressure_kpa: float
    co2_ppm: float
    velocity_ms: float
    acceleration_ms2: float
    rssi_dbm: float
    snr_db: float

    # Metadatos de la lectura (generados por el backend, no por el CanSat)
    sequence: int
    mission_time_s: float
    received_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ProcessedTelemetry:
    """
    Resultado de pasar una TelemetryReading por el procesador
    (Incremento 1): valida rangos y agrega el estado resultante.
    """

    reading: TelemetryReading
    valid: bool
    warnings: list[str]

    def to_dict(self) -> dict:
        return {
            **self.reading.to_dict(),
            "valid": self.valid,
            "warnings": self.warnings,
        }
