import { useCallback, useEffect, useState } from "react";
import { API_URL, errorMessage, request } from "../api";

const POLL_WHILE_RECORDING_MS = 3000;

export function missionExportUrl(missionId, format = "csv") {
  return `${API_URL}/api/missions/${missionId}/export.${format}`;
}

/**
 * Misiones guardadas en el backend (Prototipo 6): lista, inicio y cierre.
 * Mientras hay una misión grabando, refresca la lista para mostrar cuántas
 * muestras lleva guardadas.
 */
export function useMissions() {
  const [missions, setMissions] = useState([]);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setMissions(await request("/api/missions"));
      setError(null);
    } catch (err) {
      setError(errorMessage(err));
    }
  }, []);

  // Carga inicial (la bandera evita actualizar estado si el componente se desmonta).
  useEffect(() => {
    let cancelled = false;
    request("/api/missions")
      .then((data) => {
        if (cancelled) return;
        setMissions(data);
        setError(null);
      })
      .catch((err) => {
        if (!cancelled) setError(errorMessage(err));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const active = missions.find((m) => m.ended_at === null) ?? null;
  const activeId = active?.id ?? null;

  useEffect(() => {
    if (activeId === null) return undefined;
    const timer = setInterval(refresh, POLL_WHILE_RECORDING_MS);
    return () => clearInterval(timer);
  }, [activeId, refresh]);

  // Ejecuta una acción, refresca la lista y devuelve true si salió bien.
  const run = useCallback(
    async (action) => {
      setBusy(true);
      try {
        await action();
        await refresh();
        return true;
      } catch (err) {
        setError(errorMessage(err));
        return false;
      } finally {
        setBusy(false);
      }
    },
    [refresh],
  );

  const start = useCallback(
    (name) =>
      run(() =>
        request("/api/missions", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name }),
        }),
      ),
    [run],
  );

  const end = useCallback(
    (missionId) => run(() => request(`/api/missions/${missionId}/end`, { method: "POST" })),
    [run],
  );

  return { missions, active, error, busy, start, end };
}
