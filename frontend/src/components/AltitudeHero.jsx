export default function AltitudeHero({ latest, phase }) {
  const altitude = latest?.altitude_m;
  const velocity = latest?.velocity_ms;

  return (
    <section className="altitude-hero">
      <div className="altitude-hero__reading">
        <span className="label">Altitud</span>
        <span className="altitude-hero__value mono">
          {altitude != null ? altitude.toFixed(1) : "---.-"}
          <span className="unit">m</span>
        </span>
        <span className="altitude-hero__velocity mono">
          {velocity != null
            ? `${velocity >= 0 ? "▲" : "▼"} ${Math.abs(velocity).toFixed(1)} m/s`
            : "sin datos de velocidad"}
        </span>
      </div>

      <div className={`altitude-hero__phase altitude-hero__phase--${phase.tone}`}>
        <span className="label">Fase</span>
        <span className="value">{phase.label}</span>
      </div>
    </section>
  );
}
