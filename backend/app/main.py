"""
Backend de la Estación Terrena CanSat.

Módulos cubiertos:
- Prototipos 1, 2, 5 y 6: fuente simulada o serial, WebSocket, misiones y
  exportación CSV y JSON.
- Prototipo 7: análisis histórico por misión (serie para gráficas y estadísticas).
- Prototipo 8: alertas y diagnóstico (señal débil, pérdida de enlace, datos
  inválidos, errores seriales); ver app/alerts.py y docs/ALERTS.md.

Ejecutar con:
    uvicorn app.main:app --reload --port 8000

Fuente activa (sin comentar código):
    TELEMETRY_SOURCE=simulator   (predeterminado)
    TELEMETRY_SOURCE=serial SERIAL_PORT=COM3 SERIAL_BAUDRATE=115200
    FRAME_PASS=571617            (opcional; vacío = no validar `pass`)

Base de datos (opcional):
    DATABASE_PATH=ruta/al/archivo.db   (predeterminado: backend/data/cansat.db)

Umbrales de alertas (opcionales; ver docs/ALERTS.md):
    ALERT_LINK_TIMEOUT_S, ALERT_RSSI_WARN_DBM, ALERT_RSSI_CRIT_DBM,
    ALERT_SNR_WARN_DB, ALERT_HYSTERESIS_DB, ALERT_INVALID_CONSECUTIVE,
    ALERT_DISCARD_WINDOW_S, ALERT_DISCARD_COUNT

Endpoints:
- WS   /ws/telemetry                    -> lecturas en tiempo real y, cada segundo,
                                           un mensaje {"type": "alerts", ...}
- GET  /api/status                      -> estado general del sistema y de la fuente
- GET  /api/telemetry/latest            -> última lectura procesada (o null si no hay)
- GET  /api/alerts                      -> alertas activas, estado del enlace y eventos
- GET  /api/alerts/config               -> umbrales de alertas en uso
- GET  /api/missions                    -> misiones guardadas (la más reciente primero)
- POST /api/missions                    -> inicia una misión (empieza a guardar)
- POST /api/missions/{id}/end           -> finaliza la misión (deja de guardar)
- GET  /api/missions/{id}/export.csv    -> descarga los datos de la misión en CSV
- GET  /api/missions/{id}/export.json   -> descarga los datos de la misión en JSON
- GET  /api/missions/{id}/telemetry     -> serie para gráficas (?max_points=1000)
- GET  /api/missions/{id}/stats         -> estadísticas básicas de la misión
"""

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .alerts import AlertConfig, AlertEngine
from .connection_manager import ConnectionManager
from .database import (
    DEFAULT_DB_PATH,
    Database,
    MissionNotFoundError,
    MissionStateError,
)
from .exporter import csv_chunks, export_filename, json_chunks

from .telemetry.processor import process
from .telemetry.serial_esp32 import DEFAULT_FRAME_PASS, SerialESP32
from .telemetry.simulator import Simulator
from .telemetry.source import TelemetrySource

logging.basicConfig(level=logging.INFO)

# Intervalo entre lecturas del Simulator (segundos). Con SerialESP32 no se
# usa para esperar: cada trama se procesa en cuanto llega.
TELEMETRY_INTERVAL_S = 1.0

# Espera tras un error inesperado en el ciclo, para no entrar en un bucle
# a toda velocidad si algo falla de forma repetida.
ERROR_RETRY_DELAY_S = 1.0

# Cada cuánto se evalúan y difunden las alertas que no dependen de que llegue
# una lectura (pérdida de enlace, puerto serial). Define la latencia máxima
# extra con la que aparece una alerta de pérdida de enlace.
ALERT_TICK_S = 1.0

manager = ConnectionManager()
latest_reading: dict | None = None

# Misión que está grabando ahora (None = se muestra en vivo pero no se guarda).
active_mission_id: int | None = None


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
                "(en el firmware del receptor es 115200; no se asume un valor "
                "por omisión)."
            )
        try:
            baudrate = int(baud_raw)
        except ValueError as exc:
            raise RuntimeError(
                f"SERIAL_BAUDRATE inválido: {baud_raw!r}"
            ) from exc
        # FRAME_PASS: valor esperado del campo `pass` (p0). Sin definir se usa el
        # confirmado en el firmware del receptor; vacío = no validar.
        frame_pass = os.environ.get("FRAME_PASS", DEFAULT_FRAME_PASS).strip() or None
        return SerialESP32(
            port=port, baudrate=baudrate, expected_pass=frame_pass
        )
    raise RuntimeError(
        f"TELEMETRY_SOURCE desconocido: {kind!r} (use simulator o serial)"
    )


def create_alert_engine() -> AlertEngine:
    """Crea el motor de alertas con los umbrales de las variables ALERT_*."""
    try:
        config = AlertConfig.from_env()
    except ValueError as exc:
        raise RuntimeError(f"Configuración de alertas inválida: {exc}") from exc
    return AlertEngine(config)


source = create_source()
db = Database(os.environ.get("DATABASE_PATH") or DEFAULT_DB_PATH)
alert_engine = create_alert_engine()


def alerts_message() -> dict:
    """Estado actual de las alertas, listo para enviarse por WebSocket o REST."""
    return alert_engine.snapshot(time.monotonic())


async def telemetry_loop() -> None:
    """
    Tarea de fondo: lee de la fuente activa, procesa cada lectura, la
    difunde a todos los clientes WebSocket conectados y, si hay una misión
    activa, la guarda en SQLite.

    Esta función no sabe (ni le importa) si `source` es un Simulator o
    un SerialESP32: solo depende de la interfaz TelemetrySource
    (ver telemetry/source.py). El ritmo lo marca `source.poll_interval_s`:
    el Simulator pide esperar 1 s; SerialESP32 pide 0 porque su read()
    ya bloquea hasta que llega una trama real.
    """
    global latest_reading
    while True:
        try:
            reading = await source.read()
            processed = process(reading)
            latest_reading = processed.to_dict()
            latest_reading["source_connected"] = source.is_connected()

            # Prototipo 8: cada lectura válida de formato alimenta las alertas.
            alert_engine.on_reading(latest_reading, time.monotonic())

            if manager.client_count > 0:
                await manager.broadcast(latest_reading)

            # Guardar después de difundir: un fallo de disco no debe frenar
            # la vista en vivo.
            mission_id = active_mission_id
            if mission_id is not None:
                try:
                    await asyncio.to_thread(
                        db.insert_telemetry, mission_id, latest_reading
                    )
                except Exception:
                    logging.exception(
                        "no se pudo guardar la lectura (misión %s)", mission_id
                    )
        except Exception:
            logging.exception("error en el ciclo de telemetría; se reintenta")
            await asyncio.sleep(ERROR_RETRY_DELAY_S)
            continue

        await asyncio.sleep(source.poll_interval_s)


async def alerts_loop() -> None:
    """
    Tarea de fondo (Prototipo 8): cada `ALERT_TICK_S` evalúa las alertas que
    no dependen de que llegue una lectura (pérdida de enlace, puerto serial,
    tramas descartadas) y difunde el estado a los clientes conectados.
    Un fallo aquí se registra y no afecta a la telemetría en vivo.
    """
    while True:
        try:
            alert_engine.tick(
                time.monotonic(), source.is_connected(), source.diagnostics()
            )
            if manager.client_count > 0:
                await manager.broadcast(alerts_message())
        except Exception:
            logging.exception("error en el ciclo de alertas; se reintenta")
        await asyncio.sleep(ALERT_TICK_S)


@asynccontextmanager
async def lifespan(app: FastAPI):
    closed = await asyncio.to_thread(db.close_orphan_missions)
    if closed:
        logging.warning(
            "se cerraron %d misión(es) que habían quedado activas por un "
            "apagado inesperado",
            closed,
        )
    tasks = [
        asyncio.create_task(telemetry_loop()),
        asyncio.create_task(alerts_loop()),
    ]
    yield
    for task in tasks:
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
        "active_mission_id": active_mission_id,
        "link": alert_engine.link_state(),
    }


@app.get("/api/telemetry/latest")
async def get_latest_telemetry():
    return latest_reading


# ---------------------------------------------------------------------------
# Alertas y diagnóstico (Prototipo 8)
# ---------------------------------------------------------------------------


@app.get("/api/alerts")
async def get_alerts():
    return alerts_message()


@app.get("/api/alerts/config")
async def get_alerts_config():
    return alert_engine.config.to_dict()


# ---------------------------------------------------------------------------
# Misiones (Prototipo 6)
# ---------------------------------------------------------------------------


class MissionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    notes: str | None = Field(default=None, max_length=500)


@app.get("/api/missions")
async def list_missions():
    return await asyncio.to_thread(db.list_missions)


@app.post("/api/missions", status_code=201)
async def create_mission(body: MissionCreate):
    global active_mission_id
    name = body.name.strip()
    if not name:
        raise HTTPException(
            status_code=422, detail="El nombre de la misión no puede estar vacío."
        )
    try:
        mission = await asyncio.to_thread(db.create_mission, name, body.notes)
    except MissionStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    active_mission_id = mission["id"]
    return mission


@app.post("/api/missions/{mission_id}/end")
async def end_mission(mission_id: int):
    global active_mission_id
    try:
        mission = await asyncio.to_thread(db.end_mission, mission_id)
    except MissionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except MissionStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if active_mission_id == mission_id:
        active_mission_id = None
    return mission


@app.get("/api/missions/{mission_id}/export.csv")
async def export_mission_csv(mission_id: int):
    try:
        mission = await asyncio.to_thread(db.get_mission, mission_id)
    except MissionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    filename = export_filename(mission)
    return StreamingResponse(
        csv_chunks(db, mission_id),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/missions/{mission_id}/export.json")
async def export_mission_json(mission_id: int):
    try:
        mission = await asyncio.to_thread(db.get_mission, mission_id)
    except MissionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    filename = export_filename(mission, "json")
    return StreamingResponse(
        json_chunks(db, mission),
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# Análisis histórico (Prototipo 7)
# ---------------------------------------------------------------------------


@app.get("/api/missions/{mission_id}/telemetry")
async def get_mission_telemetry(
    mission_id: int,
    max_points: int = Query(default=1000, ge=10, le=5000),
):
    try:
        return await asyncio.to_thread(db.fetch_series, mission_id, max_points)
    except MissionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/missions/{mission_id}/stats")
async def get_mission_stats(mission_id: int):
    try:
        return await asyncio.to_thread(db.mission_stats, mission_id)
    except MissionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.websocket("/ws/telemetry")
async def telemetry_ws(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Al conectar, si ya hay una lectura reciente, se envía de inmediato
        # para que el frontend no espere hasta el siguiente ciclo. Lo mismo
        # con el estado de las alertas.
        if latest_reading is not None:
            await websocket.send_json(latest_reading)
        await websocket.send_json(alerts_message())

        while True:
            # No se espera nada del cliente; se mantiene la conexión viva.
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
