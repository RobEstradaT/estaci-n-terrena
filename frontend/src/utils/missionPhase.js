/**
 * Deriva una fase de misión legible a partir del historial de telemetría.
 *
 * Esto es una inferencia hecha en el frontend a partir de altitud/velocidad
 * para fines de visualización; el CanSat real no transmite una "fase" como
 * tal (no está en PROTOCOL.md), así que esto no debe tratarse como un dato
 * confirmado del protocolo, solo como ayuda visual para leer el vuelo.
 */
export function deriveMissionPhase(history) {
  if (history.length === 0) {
    return { label: "SIN DATOS", tone: "muted" };
  }
  if (history.length < 3) {
    return { label: "INICIANDO", tone: "muted" };
  }

  const latest = history[history.length - 1];
  const maxAltitude = Math.max(...history.map((h) => h.altitude_m));

  if (latest.altitude_m < 3) {
    return maxAltitude > 50
      ? { label: "ATERRIZADO", tone: "nominal" }
      : { label: "EN RAMPA", tone: "muted" };
  }

  if (latest.velocity_ms > 1.5) {
    return { label: "ASCENSO", tone: "signal" };
  }
  if (latest.velocity_ms < -1.5) {
    return { label: "DESCENSO", tone: "warning" };
  }
  return { label: "APOGEO", tone: "signal" };
}
