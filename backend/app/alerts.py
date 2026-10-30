"""
Alertas y diagnóstico (Prototipo 2).

Responsabilidad: a partir de las lecturas procesadas y del estado de la
fuente de datos, decidir qué alertas están activas, registrar cuándo se
activan y se resuelven, y entregar un resumen (`snapshot`) listo para
enviarse al frontend. No conoce FastAPI, WebSocket, SQLite ni el puerto
serial: recibe diccionarios y números, así que se prueba sin hardware.

Alertas (ver docs/ALERTS.md):
- WEAK_RSSI          señal débil (RSSI), con dos niveles: aviso y crítica.
- LOW_SNR            relación señal/ruido baja.
- LINK_LOST          no llegan tramas válidas desde hace más de un tiempo límite.
- INVALID_DATA       varias lecturas consecutivas con valores fuera de rango.
- SERIAL_UNAVAILABLE el puerto serial no está disponible o se desconectó.
- FRAME_ERRORS       se están descartando tramas corruptas con frecuencia.

Decisiones de diseño:
- Los umbrales son configurables (variables de entorno `ALERT_*`) y sus
  valores por omisión son PROVISIONALES: dependen de la configuración
  LoRa real (factor de dispersión, ancho de banda) y de la frecuencia de
  transmisión del CanSat, que siguen [PENDIENTE DE CONFIRMAR].
- Histéresis en RSSI y SNR: una alerta se resuelve solo cuando el valor
  supera el umbral por un margen, para que no parpadee con el ruido.
- "Pérdida de enlace" solo existe después de haber recibido al menos una
  trama; antes el estado es "waiting" (es lo normal antes del lanzamiento).
- Las alertas viven en memoria (no se guardan en SQLite).
- El motor no lee el reloj por su cuenta: recibe `now` (segundos
  monotónicos) en cada llamada, de modo que las pruebas controlan el tiempo.
"""

from __future__ import annotations

import logging
import math
import os
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Callable, Mapping

logger = logging.getLogger(__name__)

WARNING = "warning"
CRITICAL = "critical"

WEAK_RSSI = "WEAK_RSSI"
LOW_SNR = "LOW_SNR"
LINK_LOST = "LINK_LOST"
INVALID_DATA = "INVALID_DATA"
SERIAL_UNAVAILABLE = "SERIAL_UNAVAILABLE"
FRAME_ERRORS = "FRAME_ERRORS"

# Estados del enlace con el CanSat (distinto de la conexión navegador-backend).
LINK_WAITING = "waiting"
LINK_OK = "ok"
LINK_LOST_STATE = "lost"

EVENT_HISTORY = 50        # eventos que se conservan en memoria
EVENTS_IN_SNAPSHOT = 20   # eventos que se envían al frontend

# Variable de entorno -> (campo de AlertConfig, tipo)
_ENV_FIELDS = {
    "ALERT_LINK_TIMEOUT_S": ("link_timeout_s", float),
    "ALERT_RSSI_WARN_DBM": ("rssi_warn_dbm", float),
    "ALERT_RSSI_CRIT_DBM": ("rssi_crit_dbm", float),
    "ALERT_SNR_WARN_DB": ("snr_warn_db", float),
    "ALERT_HYSTERESIS_DB": ("hysteresis_db", float),
    "ALERT_INVALID_CONSECUTIVE": ("invalid_consecutive", int),
    "ALERT_DISCARD_WINDOW_S": ("discard_window_s", float),
    "ALERT_DISCARD_COUNT": ("discard_count", int),
}


@dataclass(frozen=True)
class AlertConfig:
    """Umbrales de las alertas. Valores por omisión PROVISIONALES (ver ALERTS.md)."""

    link_timeout_s: float = 5.0        # silencio máximo antes de LINK_LOST
    rssi_warn_dbm: float = -100.0      # RSSI <= este valor: aviso
    rssi_crit_dbm: float = -110.0      # RSSI <= este valor: crítica
    snr_warn_db: float = 0.0           # SNR <= este valor: aviso
    hysteresis_db: float = 3.0         # margen para resolver RSSI/SNR
    invalid_consecutive: int = 3       # lecturas inválidas seguidas para alertar
    discard_window_s: float = 10.0     # ventana para contar tramas descartadas
    discard_count: int = 3             # descartes en la ventana para alertar

    def __post_init__(self) -> None:
        for name in (
            "link_timeout_s",
            "rssi_warn_dbm",
            "rssi_crit_dbm",
            "snr_warn_db",
            "hysteresis_db",
            "discard_window_s",
        ):
            if not math.isfinite(getattr(self, name)):
                raise ValueError(f"{name} debe ser un número finito")
        if self.link_timeout_s <= 0:
            raise ValueError("link_timeout_s debe ser mayor que 0")
        if self.rssi_crit_dbm >= self.rssi_warn_dbm:
            raise ValueError(
                "rssi_crit_dbm debe ser menor que rssi_warn_dbm "
                f"(recibido crit={self.rssi_crit_dbm}, warn={self.rssi_warn_dbm})"
            )
        if self.hysteresis_db < 0:
            raise ValueError("hysteresis_db no puede ser negativa")
        if self.invalid_consecutive < 1:
            raise ValueError("invalid_consecutive debe ser al menos 1")
        if self.discard_window_s <= 0:
            raise ValueError("discard_window_s debe ser mayor que 0")
        if self.discard_count < 1:
            raise ValueError("discard_count debe ser al menos 1")

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "AlertConfig":
        """Lee los umbrales de variables `ALERT_*`; las no definidas usan el valor por omisión."""
        env = os.environ if env is None else env
        values: dict = {}
        for env_name, (attr, cast) in _ENV_FIELDS.items():
            raw = env.get(env_name, "").strip()
            if not raw:
                continue
            try:
                values[attr] = cast(raw)
            except ValueError as exc:
                raise ValueError(
                    f"{env_name} inválida: {raw!r} (se esperaba {cast.__name__})"
                ) from exc
        return cls(**values)

    def to_dict(self) -> dict:
        return asdict(self)


def _next_level(value: float, warn: float, crit: float, hysteresis: float, current: int) -> int:
    """
    Nivel de alerta (0 = ninguna, 1 = aviso, 2 = crítica) para una magnitud en
    la que un valor MENOR es peor (RSSI, SNR), con histéresis.

    Sube en cuanto el valor cruza un umbral; baja solo cuando supera el umbral
    de su nivel por más del margen de histéresis.
    """
    thresholds = {1: warn, 2: crit}
    raised = 2 if value <= crit else 1 if value <= warn else 0
    level = current
    while level > 0 and value > thresholds[level] + hysteresis:
        level -= 1
    return max(level, raised)


class AlertEngine:
    def __init__(
        self,
        config: AlertConfig | None = None,
        wall_clock: Callable[[], str] | None = None,
    ):
        self.config = config or AlertConfig()
        self._wall = wall_clock or (lambda: datetime.now(timezone.utc).isoformat())
        self._active: dict[str, dict] = {}
        self._events: deque[dict] = deque(maxlen=EVENT_HISTORY)
        self._last_frame_at: float | None = None
        self._rssi_level = 0
        self._snr_level = 0
        self._invalid_streak = 0
        self._diagnostics: dict = {}
        self._discards_seen = 0
        self._discard_times: deque[float] = deque()

    # ------------------------------------------------------------------
    # Entradas
    # ------------------------------------------------------------------

    def on_reading(self, reading: dict, now: float) -> None:
        """Evalúa una lectura procesada (`ProcessedTelemetry.to_dict()`)."""
        self._last_frame_at = now
        self._set(LINK_LOST, None, "")

        cfg = self.config
        self._rssi_level = _next_level(
            reading["rssi_dbm"],
            cfg.rssi_warn_dbm,
            cfg.rssi_crit_dbm,
            cfg.hysteresis_db,
            self._rssi_level,
        )
        if self._rssi_level == 2:
            self._set(
                WEAK_RSSI,
                CRITICAL,
                f"RSSI muy bajo (≤ {cfg.rssi_crit_dbm:g} dBm): posible pérdida de enlace inminente",
            )
        elif self._rssi_level == 1:
            self._set(WEAK_RSSI, WARNING, f"RSSI bajo (≤ {cfg.rssi_warn_dbm:g} dBm): enlace degradado")
        else:
            self._set(WEAK_RSSI, None, "")

        self._snr_level = _next_level(
            reading["snr_db"],
            cfg.snr_warn_db,
            float("-inf"),
            cfg.hysteresis_db,
            self._snr_level,
        )
        if self._snr_level >= 1:
            self._set(LOW_SNR, WARNING, f"SNR bajo (≤ {cfg.snr_warn_db:g} dB): poco margen de demodulación")
        else:
            self._set(LOW_SNR, None, "")

        if reading["valid"]:
            self._invalid_streak = 0
        else:
            self._invalid_streak += 1
        if self._invalid_streak >= cfg.invalid_consecutive:
            warnings = reading.get("warnings") or []
            detail = f": {warnings[0]}" if warnings else ""
            self._set(
                INVALID_DATA,
                WARNING,
                f"{self._invalid_streak} lecturas consecutivas con datos fuera de rango{detail}",
            )
        elif self._invalid_streak == 0:
            self._set(INVALID_DATA, None, "")

    def tick(self, now: float, source_connected: bool, diagnostics: Mapping | None = None) -> None:
        """
        Evaluación periódica (independiente de que lleguen lecturas): pérdida
        de enlace, puerto serial y tramas descartadas. Se llama ~1 vez por segundo.
        """
        cfg = self.config
        self._diagnostics = dict(diagnostics or {})

        if (
            self._last_frame_at is not None
            and now - self._last_frame_at > cfg.link_timeout_s
        ):
            self._set(
                LINK_LOST,
                CRITICAL,
                f"Sin tramas válidas desde hace más de {cfg.link_timeout_s:g} s",
            )
            # Las lecturas anteriores ya no describen el estado actual.
            self._clear_signal_alerts()

        if source_connected:
            self._set(SERIAL_UNAVAILABLE, None, "")
        else:
            self._set(
                SERIAL_UNAVAILABLE,
                CRITICAL,
                "Puerto serial no disponible o desconectado",
            )

        self._update_discards(now, int(self._diagnostics.get("frames_discarded", 0)))

    # ------------------------------------------------------------------
    # Salida
    # ------------------------------------------------------------------

    def link_state(self) -> str:
        if self._last_frame_at is None:
            return LINK_WAITING
        return LINK_LOST_STATE if LINK_LOST in self._active else LINK_OK

    def snapshot(self, now: float) -> dict:
        """Resumen para el frontend (mensaje `type: "alerts"` del WebSocket)."""
        active = sorted(
            self._active.values(),
            key=lambda a: (0 if a["severity"] == CRITICAL else 1, a["since"]),
        )
        since_last = (
            None if self._last_frame_at is None else round(now - self._last_frame_at, 1)
        )
        return {
            "type": "alerts",
            "link": self.link_state(),
            "seconds_since_last_frame": since_last,
            "active": [dict(a) for a in active],
            "events": list(reversed(self._events))[:EVENTS_IN_SNAPSHOT],
            "diagnostics": dict(self._diagnostics),
        }

    # ------------------------------------------------------------------
    # Internos
    # ------------------------------------------------------------------

    def _update_discards(self, now: float, total: int) -> None:
        cfg = self.config
        if total > self._discards_seen:
            self._discard_times.extend([now] * (total - self._discards_seen))
        # Si el total baja, la fuente se reinició: se toma como nueva base.
        self._discards_seen = total
        while self._discard_times and now - self._discard_times[0] > cfg.discard_window_s:
            self._discard_times.popleft()

        recent = len(self._discard_times)
        if recent >= cfg.discard_count:
            self._set(
                FRAME_ERRORS,
                WARNING,
                f"{recent} tramas descartadas en los últimos {cfg.discard_window_s:g} s "
                "(formato, pass o valores inválidos)",
            )
        elif recent == 0:
            self._set(FRAME_ERRORS, None, "")

    def _clear_signal_alerts(self) -> None:
        self._rssi_level = 0
        self._snr_level = 0
        self._invalid_streak = 0
        for code in (WEAK_RSSI, LOW_SNR, INVALID_DATA):
            self._set(code, None, "")

    def _set(self, code: str, severity: str | None, message: str) -> None:
        """Activa, escala o resuelve una alerta; registra solo los cambios."""
        current = self._active.get(code)
        if severity is None:
            if current is not None:
                del self._active[code]
                self._emit(code, current["severity"], "cleared", current["message"])
            return
        if current is None or current["severity"] != severity:
            self._active[code] = {
                "code": code,
                "severity": severity,
                "message": message,
                "since": self._wall(),
            }
            self._emit(code, severity, "raised", message)

    def _emit(self, code: str, severity: str, state: str, message: str) -> None:
        self._events.append(
            {
                "code": code,
                "severity": severity,
                "state": state,
                "message": message,
                "at": self._wall(),
            }
        )
        log = logger.warning if state == "raised" else logger.info
        log("alerta %s %s (%s): %s", code, state, severity, message)
