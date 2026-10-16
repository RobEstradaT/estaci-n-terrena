export default function InstrumentCard({ label, value, unit, flagged }) {
  return (
    <div className={`instrument-card ${flagged ? "instrument-card--warning" : ""}`}>
      <span className="label">{label}</span>
      <span className="instrument-card__value mono">
        {value}
        {unit && <span className="unit">{unit}</span>}
      </span>
    </div>
  );
}
