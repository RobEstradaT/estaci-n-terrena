"""
Backend de la Estación Terrena CanSat.

Incrementos cubiertos por este archivo:
- Incremento 1: fuente simulada + procesamiento inicial.
- Incremento 2: FastAPI + WebSocket en tiempo real.
- Incremento 5: selección de fuente Simulator | SerialESP32.

Ejecutar con:
    uvicorn app.main:app --reload --port 8000

Fuente activa (sin comentar código):
    TELEMETRY_SOURCE=simulator   (predeterminado)
    TELEMETRY_SOURCE=serial SERIAL_PORT=COM3 SERIAL_BAUDRATE=115200

Endpoints:
- WS   /ws/telemetry        -> stream de telemetría procesada en tiempo real
- GET  /api/status          -> estado general del sistema y de la fuente
- GET  /api/telemetry/latest -> última lectura procesada (o null si no hay)
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .connection_manager import ConnectionManager
from .telemetry.processor import process
from .telemetry.serial_esp32 import SerialESP32
from .telemetry.simulator import Simulator
from .telemetry.source import TelemetrySource

logging.basicConfig(level=logging.INFO)

# Intervalo entre lecturas de telemetría (segundos).
TELEMETRY_INTERVAL_S = 1.0

manager = ConnectionManager()
latest_reading: dict | None = None


def create_source() -> TelemetrySource:
    """Elige Simulator o SerialESP32 según TELEMETRY_SOURCE."""
    kind = os.environ.get("TELEMETRY_SOURCE", "simulator").strip().lower()
    if kind in ("simulator", "sim", ""):
        return Simulator(dt_s=TELEMETRY_INTERVAL_S)
    if kind == "serial":
        port = os.environ.get("SERIAL_PORT", "").strip()
        baud_raw = os.environ.get("SERIAL_BAUDRATE", "").strip()
        if not port or not baud_raw:
            raise RuntimeError(
                "TELEMETRY_SOURCE=serial requiere SERIAL_PORT y SERIAL_BAUDRATE "
                "(el baudrate del ESP32 no está confirmado en PROTOCOL.md; "
                "no se asume un valor fijo)."
            )
        try:
            baudrate = int(baud_raw)
        except ValueError as exc:
            raise RuntimeError(
                f"SERIAL_BAUDRATE inválido: {baud_raw!r}"
            ) from exc
        return SerialESP32(port=port, baudrate=baudrate)
    raise RuntimeError(
        f"TELEMETRY_SOURCE desconocido: {kind!r} (use simulator o serial)"
    )


source = create_source()


async def telemetry_loop() -> None:
    """
    Tarea de fondo: lee de la fuente activa, procesa cada lectura y la
    difunde a todos los clientes WebSocket conectados.

    Esta función no sabe (ni le importa) si `source` es un Simulator o
    un SerialESP32: solo depende de la interfaz TelemetrySource
    (ver telemetry/source.py).
    """
    global latest_reading
    while True:
        try:
            reading = await source.read()
            processed = process(reading)
            latest_reading = processed.to_dict()
            latest_reading["source_connected"] = source.is_connected()

            if manager.client_count > 0:
                await manager.broadcast(latest_reading)
        except Exception:
            logging.exception("error en el ciclo de telemetría; se reintenta")

        await asyncio.sleep(TELEMETRY_INTERVAL_S)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(telemetry_loop())
    yield
    task.cancel()
    close = getattr(source, "close", None)
    if callable(close):
        close()


app = FastAPI(title="Estación Terrena CanSat", lifespan=lifespan)

# CORS abierto para desarrollo local (frontend en otro puerto/host de Vite).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/status")
async def get_status():
    return {
        "backend": "ok",
        "source_type": type(source).__name__,
        "source_connected": source.is_connected(),
        "connected_clients": manager.client_count,
        "telemetry_interval_s": TELEMETRY_INTERVAL_S,
    }


@app.get("/api/telemetry/latest")
async def get_latest_telemetry():
    return latest_reading


@app.websocket("/ws/telemetry")
async def telemetry_ws(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Al conectar, si ya hay una lectura reciente, se envía de inmediato
        # para que el frontend no espere hasta el siguiente ciclo.
        if latest_reading is not None:
            await websocket.send_json(latest_reading)

        while True:
            # No se espera nada del cliente; se mantiene la conexión viva.
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
