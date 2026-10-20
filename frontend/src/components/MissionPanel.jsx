import { useState } from "react";
import { missionExportUrl, useMissions } from "../hooks/useMissions";
import "./MissionPanel.css";

const RECENT_LIMIT = 8;

function formatDateTime(iso) {
  return new Date(iso).toLocaleString("es-MX", {
    dateStyle: "short",
    timeStyle: "medium",
  });
}

function sampleLabel(count) {
  return count === 1 ? "1 muestra" : `${count} muestras`;
}

export default function MissionPanel() {
  const { missions, active, error, busy, start, end } = useMissions();
  const [name, setName] = useState("");

  async function handleStart(event) {
    event.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) return;
    if (await start(trimmed)) setName("");
  }

  const finished = missions.filter((m) => m.ended_at !== null).slice(0, RECENT_LIMIT);

  return (
    <section className="mission-panel" aria-label="Misiones">
      <div className="mission-panel__bar">
        <div className="mission-panel__state">
          <span className="label">Misión</span>
          {active ? (
            <span className="mission-panel__recording">
              <span className="mission-panel__dot" aria-hidden="true" />
              <strong>{active.name}</strong>
              <span className="mission-panel__count mono">
                {sampleLabel(active.sample_count)}
              </span>
            </span>
          ) : (
            <span className="mission-panel__idle">
              Sin misión activa: los datos se ven en vivo pero no se guardan
            </span>
          )}
        </div>

        {active ? (
          <button
            type="button"
            className="mission-btn mission-btn--stop"
            onClick={() => end(active.id)}
            disabled={busy}
          >
            Finalizar misión
          </button>
        ) : (
          <form className="mission-panel__new" onSubmit={handleStart}>
            <input
              className="mission-input"
              type="text"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Nombre de la misión"
              maxLength={100}
              aria-label="Nombre de la misión"
              disabled={busy}
            />
            <button
              type="submit"
              className="mission-btn mission-btn--start"
              disabled={busy || name.trim() === ""}
            >
              Nueva misión
            </button>
          </form>
        )}
      </div>

      {error && (
        <p className="mission-panel__error" role="alert">
          {error}
        </p>
      )}

      {finished.length > 0 && (
        <ul className="mission-list">
          {finished.map((mission) => (
            <li key={mission.id} className="mission-list__item">
              <span className="mission-list__name">{mission.name}</span>
              <span className="mission-list__meta mono">
                {formatDateTime(mission.started_at)}
              </span>
              <span className="mission-list__meta mono">
                {sampleLabel(mission.sample_count)}
              </span>
              <a className="mission-list__export" href={missionExportUrl(mission.id)}>
                Exportar CSV
              </a>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
