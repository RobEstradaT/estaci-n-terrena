"""
Fuente de datos simulada (Prototipo 1).

Genera telemetría sintética que sigue un perfil de vuelo aproximado
(ascenso, apogeo, descenso bajo paracaídas, aterrizaje) para poder
desarrollar y probar todo el pipeline sin depender del hardware real.

Los valores concretos (velocidad de ascenso, altitud máxima, tasa de
descenso, etc.) son PROVISIONALES y solo buscan producir una señal
realista para pruebas; no representan mediciones ni especificaciones
del CanSat real.

Unidades y variables alineadas con el protocolo confirmado en
PROTOCOL.md: presión en kPa (no hPa) e incluye `acceleration_ms2`
(aceleración total), variable que se sumó al confirmarse el protocolo.
"""

import math
import random
from .schema import TelemetryReading
from .source import TelemetrySource

# --- Parámetros del perfil de vuelo simulado (provisionales) ---
LAUNCH_ALTITUDE_M = 0.0
APOGEE_ALTITUDE_M = 1000.0
ASCENT_DURATION_S = 35.0        # motor + coast hasta apogeo
DESCENT_RATE_MS = 6.5           # descenso bajo paracaídas (aprox.)
GROUND_TEMP_C = 22.0
LAPSE_RATE_C_PER_M = 0.0065     # gradiente térmico estándar
SEA_LEVEL_PRESSURE_KPA = 101.325
GRAVITY_MS2 = 9.8                # usada para modelar la aceleración total (magnitud), no solo la vertical
MAX_RANGE_M = 1000.0            # alcance máximo del enlace LoRa (ver memoria del proyecto)


class Simulator(TelemetrySource):
    """
    Genera una TelemetryReading cada vez que se llama a `read()`.

    El "tiempo de misión" avanza `dt_s` segundos por cada lectura
    (independiente de la velocidad real a la que se invoque `read`),
    para que el perfil de vuelo sea reproducible y configurable.
    """

    def __init__(self, dt_s: float = 1.0, seed: int | None = None):
        self._dt_s = dt_s
        # El simulador no bloquea: el ciclo del backend debe esperar dt_s
        # entre lecturas para emitir ~1 muestra por intervalo.
        self.poll_interval_s = dt_s
        self._mission_time_s = 0.0
        self._sequence = 0
        self._rng = random.Random(seed)
        self._connected = True
        self._descent_start_altitude = APOGEE_ALTITUDE_M
        self._prev_velocity_ms = 0.0

    def is_connected(self) -> bool:
        return self._connected

    def _altitude_at(self, t: float) -> float:
        if t <= ASCENT_DURATION_S:
            # Ascenso: curva suave (smoothstep) con aceleración y
            # desaceleración graduales hasta el apogeo.
            progress = t / ASCENT_DURATION_S
            return APOGEE_ALTITUDE_M * (3 * progress**2 - 2 * progress**3)

        # Descenso bajo paracaídas a tasa aproximadamente constante.
        t_descent = t - ASCENT_DURATION_S
        altitude = APOGEE_ALTITUDE_M - DESCENT_RATE_MS * t_descent
        return max(altitude, 0.0)

    def _velocity_at(self, t: float, altitude_now: float, altitude_prev: float) -> float:
        # Velocidad vertical aproximada a partir del cambio de altitud.
        return (altitude_now - altitude_prev) / self._dt_s

    async def read(self) -> TelemetryReading:
        t_prev = self._mission_time_s
        alt_prev = self._altitude_at(t_prev)

        self._mission_time_s += self._dt_s
        t = self._mission_time_s
        altitude = self._altitude_at(t)

        velocity = self._velocity_at(t, altitude, alt_prev)
        velocity += self._rng.gauss(0, 0.15)  # ruido de sensor

        temperature = GROUND_TEMP_C - LAPSE_RATE_C_PER_M * altitude
        temperature += self._rng.gauss(0, 0.3)

        pressure = SEA_LEVEL_PRESSURE_KPA * math.exp(-altitude / 8434.0)
        pressure += self._rng.gauss(0, 0.05)

        # Aceleración total (magnitud, como la reportaría un acelerómetro):
        # combina la aceleración dinámica vertical (derivada numérica de la
        # velocidad) con la componente de gravedad, que domina cuando el
        # CanSat se mueve a velocidad aproximadamente constante.
        dv_dt = (velocity - self._prev_velocity_ms) / self._dt_s
        acceleration = math.sqrt(dv_dt**2 + GRAVITY_MS2**2)
        acceleration += self._rng.gauss(0, 0.3)
        acceleration = max(acceleration, 0.0)
        self._prev_velocity_ms = velocity

        co2 = 420.0 + self._rng.gauss(0, 8.0)
        co2 = max(co2, 0.0)

        # Distancia aproximada al receptor (se asume estación en el punto
        # de lanzamiento, por lo que la distancia ~ altitud). Se usa para
        # degradar RSSI/SNR de forma creíble cerca del límite de alcance.
        distance = max(altitude, 1.0)
        range_fraction = min(distance / MAX_RANGE_M, 1.2)

        rssi = -40.0 - 55.0 * range_fraction + self._rng.gauss(0, 2.0)
        rssi = max(min(rssi, -30.0), -120.0)

        snr = 12.0 - 15.0 * range_fraction + self._rng.gauss(0, 1.0)
        snr = max(min(snr, 15.0), -10.0)

        self._sequence += 1

        return TelemetryReading(
            altitude_m=round(altitude, 2),
            temperature_c=round(temperature, 2),
            pressure_kpa=round(pressure, 2),
            co2_ppm=round(co2, 2),
            velocity_ms=round(velocity, 2),
            acceleration_ms2=round(acceleration, 2),
            rssi_dbm=round(rssi, 1),
            snr_db=round(snr, 1),
            sequence=self._sequence,
            mission_time_s=round(t, 1),
        )

    def reset(self) -> None:
        """Reinicia la simulación (útil para repetir una demo)."""
        self._mission_time_s = 0.0
        self._sequence = 0
