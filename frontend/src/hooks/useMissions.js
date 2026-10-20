import { useCallback, useEffect, useState } from "react";

const API_URL = "http://localhost:8000";
const POLL_WHILE_RECORDING_MS = 3000;

export function missionExportUrl(missionId) {
  return `${API_URL}/api/missions/${missionId}/export.csv`;
}

function errorMessage(err) {
  return err instanceof TypeError ? "No se pudo conectar con el backend." : err.message;
}

async function request(path, options) {
  const response = await fetch(`${API_URL}${path}`, options);
  if (!response.ok) {
    let message = `Error ${response.status}`;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") message = body.detail;
    } catch {
      // La respuesta no traía JSON; se queda el mensaje genérico.
    }
    throw new Error(message);
  }
  return response.json();
}

/**
 * Misiones guardadas en el backend (Incremento 6): lista, inicio y cierre.
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
