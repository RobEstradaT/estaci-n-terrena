function formatMissionClock(seconds) {
  if (seconds == null) return "--:--";
  const mins = Math.floor(seconds / 60)
    .toString()
    .padStart(2, "0");
  const secs = Math.floor(seconds % 60)
    .toString()
    .padStart(2, "0");
  return `${mins}:${secs}`;
}

const CONNECTION_LABEL = {
  connecting: "CONECTANDO",
  open: "ENLACE ACTIVO",
  closed: "SIN ENLACE",
};

export default function MissionHeader({ connectionState, latest }) {
  return (
    <header className="mission-header">
      <div className="mission-header__title">
        <span className="mission-header__eyebrow">Estación Terrena</span>
        <h1>CanSat · Monitoreo en vivo</h1>
      </div>

      <div className="mission-header__stats">
        <div className="mission-header__stat">
          <span className="label">T. de misión</span>
          <span className="value mono">
            {formatMissionClock(latest?.mission_time_s)}
          </span>
        </div>
        <div className="mission-header__stat">
          <span className="label">Paquetes</span>
          <span className="value mono">{latest?.sequence ?? "--"}</span>
        </div>
        <div className={`connection-pill connection-pill--${connectionState}`}>
          <span className="connection-pill__dot" />
          {CONNECTION_LABEL[connectionState]}
        </div>
      </div>
    </header>
  );
}
