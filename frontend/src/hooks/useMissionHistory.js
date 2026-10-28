import { useEffect, useState } from "react";
import { errorMessage, request } from "../api";

// Máximo de puntos por gráfica; el backend reduce la muestra si hay más.
const MAX_POINTS = 1000;

const EMPTY = { series: null, stats: null, error: null, loading: false };

/** Carga la serie y las estadísticas de una misión finalizada. */
export function useMissionHistory(missionId) {
  const [state, setState] = useState(EMPTY);

  useEffect(() => {
    if (missionId == null) return undefined;
    let cancelled = false;
    setState({ ...EMPTY, loading: true });

    Promise.all([
      request(`/api/missions/${missionId}/telemetry?max_points=${MAX_POINTS}`),
      request(`/api/missions/${missionId}/stats`),
    ])
      .then(([series, stats]) => {
        if (!cancelled) setState({ series, stats, error: null, loading: false });
      })
      .catch((err) => {
        if (!cancelled) setState({ ...EMPTY, error: errorMessage(err) });
      });

    return () => {
      cancelled = true;
    };
  }, [missionId]);

  return state;
}
