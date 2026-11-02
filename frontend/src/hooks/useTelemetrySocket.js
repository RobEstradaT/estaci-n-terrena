import { useEffect, useRef, useState } from "react";

const WS_URL = "ws://localhost:8000/ws/telemetry";
const HISTORY_LIMIT = 120; // ~2 minutos a 1 lectura/seg, suficiente para la gráfica en vivo
const RECONNECT_DELAY_MS = 2000;

/**
 * Se conecta al WebSocket de telemetría del backend, mantiene la última
 * lectura y un historial acotado (para las gráficas del Prototipo 4),
 * y reintenta la conexión si el backend no está disponible o se cae.
 *
 * Prototipo 8: el mismo WebSocket también trae, cada segundo, un mensaje
 * `{ type: "alerts", ... }` con alertas activas, estado del enlace y
 * diagnóstico. Ese mensaje no es una lectura: se guarda aparte y no entra
 * en `latest` ni en `history`. Si se pierde la conexión con el backend,
 * `alerts` vuelve a null para no mostrar un estado obsoleto.
 */
export function useTelemetrySocket() {
  const [latest, setLatest] = useState(null);
  const [history, setHistory] = useState([]);
  const [alerts, setAlerts] = useState(null);
  const [connectionState, setConnectionState] = useState("connecting"); // connecting | open | closed

  const socketRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);

  useEffect(() => {
    let cancelled = false;

    function connect() {
      if (cancelled) return;

      setConnectionState((prev) => (prev === "open" ? prev : "connecting"));
      const socket = new WebSocket(WS_URL);
      socketRef.current = socket;

      socket.onopen = () => {
        if (cancelled) return;
        setConnectionState("open");
      };

      socket.onmessage = (event) => {
        if (cancelled) return;
        const data = JSON.parse(event.data);

        if (data.type === "alerts") {
          setAlerts(data);
          return;
        }

        setLatest(data);
        setHistory((prev) => {
          const next = [...prev, data];
          return next.length > HISTORY_LIMIT
            ? next.slice(next.length - HISTORY_LIMIT)
            : next;
        });
      };

      socket.onclose = () => {
        if (cancelled) return;
        setConnectionState("closed");
        setAlerts(null);
        reconnectTimeoutRef.current = setTimeout(connect, RECONNECT_DELAY_MS);
      };

      socket.onerror = () => {
        socket.close();
      };
    }

    connect();

    return () => {
      cancelled = true;
      clearTimeout(reconnectTimeoutRef.current);
      socketRef.current?.close();
    };
  }, []);

  return { latest, history, alerts, connectionState };
}
