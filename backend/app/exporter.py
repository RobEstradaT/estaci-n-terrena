"""
Exportación de una misión a CSV y JSON (Prototipo 6).

Responsabilidad: convertir las lecturas guardadas de una misión en texto,
por bloques, para servirlo como descarga sin cargar toda la misión en memoria.

Formato CSV:
- Codificación UTF-8 con BOM (para que Excel respete los acentos).
- Separador de campos: coma; separador decimal: punto; fin de línea CRLF.
- `valid` es 1/0; `warnings` une las advertencias con " | ".

Formato JSON:
- Un objeto con dos claves: "mission" (metadatos) y "telemetry" (lista de
  lecturas, en el mismo orden que el CSV).
- `valid` es booleano y `warnings` es una lista de cadenas.
- UTF-8 sin BOM.

En ambos formatos los nombres de campo son los de TelemetryReading (schema.py).
"""

from __future__ import annotations

import csv
import io
import json
import re
import unicodedata
from typing import Iterator

from .database import TELEMETRY_FIELDS, Database

CSV_COLUMNS = (
    "sequence",
    "mission_time_s",
    "received_at",
    *TELEMETRY_FIELDS,
    "valid",
    "warnings",
)

BATCH_SIZE = 1000


def _format_row(row: dict) -> list:
    out = []
    for column in CSV_COLUMNS:
        value = row[column]
        if column == "warnings":
            value = " | ".join(json.loads(value))
        out.append(value)
    return out


def _json_record(row: dict) -> dict:
    record = {
        "sequence": row["sequence"],
        "mission_time_s": row["mission_time_s"],
        "received_at": row["received_at"],
    }
    for field in TELEMETRY_FIELDS:
        record[field] = row[field]
    record["valid"] = bool(row["valid"])
    record["warnings"] = json.loads(row["warnings"])
    return record


def _iter_telemetry(db: Database, mission_id: int, batch_size: int) -> Iterator[list[dict]]:
    """Entrega las lecturas de una misión por bloques, en orden de inserción."""
    after_id = 0
    while True:
        rows = db.fetch_telemetry_batch(mission_id, after_id, batch_size)
        if not rows:
            return
        yield rows
        after_id = rows[-1]["id"]


def _flush(buffer: io.StringIO) -> str:
    text = buffer.getvalue()
    buffer.seek(0)
    buffer.truncate(0)
    return text


def csv_chunks(
    db: Database, mission_id: int, batch_size: int = BATCH_SIZE
) -> Iterator[str]:
    """Genera el CSV de una misión en bloques de texto (cabecera primero)."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(CSV_COLUMNS)
    yield "\ufeff" + _flush(buffer)

    for rows in _iter_telemetry(db, mission_id, batch_size):
        for row in rows:
            writer.writerow(_format_row(row))
        yield _flush(buffer)


def json_chunks(db: Database, mission: dict, batch_size: int = BATCH_SIZE) -> Iterator[str]:
    """
    Genera el JSON de una misión en bloques de texto.

    Recibe el dict de la misión (ya validado por el llamador) para no
    consultarla de nuevo. Cada bloque es un fragmento válido del documento
    final, de modo que el resultado completo siempre se puede parsear.
    """
    head = json.dumps(mission, ensure_ascii=False)
    yield f'{{"mission": {head}, "telemetry": ['

    first = True
    for rows in _iter_telemetry(db, mission["id"], batch_size):
        parts = [json.dumps(_json_record(row), ensure_ascii=False) for row in rows]
        yield ("" if first else ",") + ",".join(parts)
        first = False

    yield "]}"


def export_filename(mission: dict, extension: str = "csv") -> str:
    """Nombre de archivo seguro: mision_<id>_<nombre-en-ascii>.<extensión>"""
    ascii_name = (
        unicodedata.normalize("NFKD", mission["name"])
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    slug = re.sub(r"[^A-Za-z0-9]+", "-", ascii_name).strip("-").lower()[:40]
    base = f"mision_{mission['id']}"
    return f"{base}_{slug}.{extension}" if slug else f"{base}.{extension}"
