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

    # Segundos que el ciclo del backend espera entre lecturas. Las fuentes
    # cuyo read() ya bloquea esperando datos reales (SerialESP32) lo dejan
    # en 0 para no acumular retraso; el Simulator lo usa para marcar su ritmo.
    poll_interval_s: float = 0.0

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

    def diagnostics(self) -> dict:
        """
        Contadores de diagnóstico de la fuente (Prototipo 2). Las claves que
        reconoce el motor de alertas son `frames_discarded`; el resto se
        muestra tal cual en la interfaz. Una fuente sin diagnóstico (el
        Simulator) devuelve un diccionario vacío.
        """
        return {}
