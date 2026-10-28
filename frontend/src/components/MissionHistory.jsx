import { useMissionHistory } from "../hooks/useMissionHistory";
import TelemetryCharts from "./TelemetryCharts";
import "./MissionHistory.css";

const STAT_ROWS = [
  { key: "altitude_m", label: "Altitud", unit: "m" },
  { key: "temperature_c", label: "Temperatura", unit: "°C" },
  { key: "pressure_kpa", label: "Presión", unit: "kPa" },
  { key: "co2_ppm", label: "CO₂", unit: "ppm" },
  { key: "velocity_ms", label: "Velocidad", unit: "m/s" },
  { key: "acceleration_ms2", label: "Aceleración total", unit: "m/s²" },
  { key: "rssi_dbm", label: "RSSI", unit: "dBm" },
  { key: "snr_db", label: "SNR", unit: "dB" },
];

function formatNumber(value) {
  return value == null ? "--" : value.toFixed(1);
}

function formatDuration(seconds) {
  if (seconds == null) return "--:--";
  const total = Math.round(seconds);
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60).toString().padStart(2, "0");
  const secs = (total % 60).toString().padStart(2, "0");
  return hours > 0 ? `${hours}:${minutes}:${secs}` : `${minutes}:${secs}`;
}

function SummaryStat({ label, value }) {
  return (
    <div className="mission-history__stat">
      <span className="label">{label}</span>
      <span className="value">{value}</span>
    </div>
  );
}

export default function MissionHistory({ mission, onClose }) {
  const { series, stats, loading, error } = useMissionHistory(mission.id);

  return (
    <section className="mission-history" aria-label={`Análisis de la misión ${mission.name}`}>
      <header className="mission-history__header">
        <div>
          <span className="label">Análisis histórico</span>
          <h2>{mission.name}</h2>
        </div>
        <button type="button" className="mission-btn" onClick={onClose}>
          Cerrar análisis
        </button>
      </header>

      {error && (
        <p className="mission-history__error" role="alert">
          {error}
        </p>
      )}
      {loading && <p className="mission-history__status">Cargando datos…</p>}

      {stats && (
        <>
          <div className="mission-history__summary">
            <SummaryStat label="Duración" value={formatDuration(stats.duration_s)} />
            <SummaryStat label="Muestras" value={stats.samples} />
            <SummaryStat label="Inválidas" value={stats.invalid_samples} />
          </div>

          <table className="mission-history__table">
            <thead>
              <tr>
                <th scope="col">Variable</th>
                <th scope="col">Mínimo</th>
                <th scope="col">Promedio</th>
                <th scope="col">Máximo</th>
              </tr>
            </thead>
            <tbody>
              {STAT_ROWS.map((row) => {
                const field = stats.fields[row.key];
                return (
                  <tr key={row.key}>
                    <td>
                      {row.label} <span className="unit">{row.unit}</span>
                    </td>
                    <td>{formatNumber(field.min)}</td>
                    <td>{formatNumber(field.avg)}</td>
                    <td>{formatNumber(field.max)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </>
      )}

      {series && series.total === 0 && (
        <p className="mission-history__status">Esta misión no tiene muestras guardadas.</p>
      )}

      {series && series.total > 0 && (
        <>
          {series.step > 1 && (
            <p className="mission-history__note">
              Gráficas con 1 de cada {series.step} muestras ({series.points.length} de{" "}
              {series.total}).
            </p>
          )}
          <TelemetryCharts history={series.points} />
        </>
      )}
    </section>
  );
}
