"""
Abstracción de fuente de datos de telemetría (ver ARCHITECTURE.md sección 3).

Toda fuente de telemetría (simulada o real) debe implementar esta interfaz
para que el resto del backend (procesamiento, WebSocket, persistencia) no
dependa de si los datos vienen de un `Simulator` o de `SerialESP32`.

`SerialESP32` (Incremento 5) lee UART línea por línea y usa `parse_frame`
para traducir la trama confirmada en PROTOCOL.md a `TelemetryReading`.
"""

from abc import ABC, abstractmethod
from .schema import TelemetryReading


class TelemetrySource(ABC):
    """Interfaz común para cualquier origen de telemetría."""

    @abstractmethod
    async def read(self) -> TelemetryReading:
        """
        Obtiene la siguiente lectura de telemetría ya estructurada.

        SerialESP32 lee una línea del puerto serial y la traduce con
        `parse_frame` (formato confirmado en PROTOCOL.md).
        """
        raise NotImplementedError

    @abstractmethod
    def is_connected(self) -> bool:
        """Indica si la fuente está actualmente recibiendo datos."""
        raise NotImplementedError
