import { useEffect, useRef, useState } from "react";

const WS_URL = "ws://localhost:8000/ws/telemetry";
const HISTORY_LIMIT = 120; // ~2 minutos a 1 lectura/seg, suficiente para la gráfica en vivo
const RECONNECT_DELAY_MS = 2000;

/**
 * Se conecta al WebSocket de telemetría del backend, mantiene la última
 * lectura y un historial acotado (para las gráficas del Incremento 4),
 * y reintenta la conexión si el backend no está disponible o se cae.
 */
export function useTelemetrySocket() {
  const [latest, setLatest] = useState(null);
  const [history, setHistory] = useState([]);
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

  return { latest, history, connectionState };
}
