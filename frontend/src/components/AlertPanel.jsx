import "./AlertPanel.css";

const SEVERITY_LABEL = { critical: "CRÍTICA", warning: "AVISO" };
const STATE_LABEL = { raised: "Activada", cleared: "Resuelta" };
const EVENTS_SHOWN = 6;

function formatTime(iso) {
  return new Date(iso).toLocaleTimeString("es-MX", { timeStyle: "medium" });
}

function DiagnosticItem({ label, value }) {
  return (
    <div className="alert-panel__diag-item">
      <span className="label">{label}</span>
      <span className="value mono">{value}</span>
    </div>
  );
}

/**
 * Alertas activas, eventos recientes y diagnóstico de la fuente (Prototipo 8).
 * Toda la información llega del backend en el mensaje `type: "alerts"`.
 */
export default function AlertPanel({ alerts }) {
  if (!alerts) {
    return (
      <section className="alert-panel" aria-label="Alertas y diagnóstico">
        <span className="label">Alertas y diagnóstico</span>
        <p className="alert-panel__idle">
          Sin conexión con el backend: no hay información de alertas.
        </p>
      </section>
    );
  }

  const { active, events, diagnostics } = alerts;
  const hasSerialDiagnostics = diagnostics && diagnostics.frames_ok != null;

  return (
    <section className="alert-panel" aria-label="Alertas y diagnóstico">
      <span className="label">Alertas y diagnóstico</span>

      {active.length === 0 ? (
        <p className="alert-panel__idle">Sin alertas activas</p>
      ) : (
        <ul className="alert-list" aria-live="polite">
          {active.map((alert) => (
            <li
              key={alert.code}
              className={`alert-list__item alert-list__item--${alert.severity}`}
            >
              <span className="alert-list__severity mono">
                {SEVERITY_LABEL[alert.severity] ?? alert.severity}
              </span>
              <span className="alert-list__message">{alert.message}</span>
              <span className="alert-list__since mono">desde {formatTime(alert.since)}</span>
            </li>
          ))}
        </ul>
      )}

      {hasSerialDiagnostics && (
        <div className="alert-panel__diag">
          <DiagnosticItem label="Tramas válidas" value={diagnostics.frames_ok} />
          <DiagnosticItem label="Descartadas" value={diagnostics.frames_discarded} />
          <DiagnosticItem label="Desconexiones" value={diagnostics.disconnects} />
          {alerts.seconds_since_last_frame != null && (
            <DiagnosticItem
              label="Última trama hace"
              value={`${alerts.seconds_since_last_frame.toFixed(1)} s`}
            />
          )}
          {diagnostics.last_error && (
            <p className="alert-panel__last-error">Último error: {diagnostics.last_error}</p>
          )}
        </div>
      )}

      {events.length > 0 && (
        <details className="alert-panel__events">
          <summary>Eventos recientes ({Math.min(events.length, EVENTS_SHOWN)})</summary>
          <ul>
            {events.slice(0, EVENTS_SHOWN).map((event, index) => (
              <li key={`${event.at}-${event.code}-${index}`}>
                <span className="mono">{formatTime(event.at)}</span>{" "}
                <strong>{STATE_LABEL[event.state] ?? event.state}</strong>: {event.message}
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}
