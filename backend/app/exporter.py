"""
Exportación de una misión a CSV (Incremento 6).

Responsabilidad: convertir las lecturas guardadas de una misión en texto
CSV, por bloques, para poder servirlo como descarga sin cargar toda la
misión en memoria.

Formato:
- Codificación UTF-8 con BOM (para que Excel respete los acentos).
- Separador de campos: coma; separador decimal: punto; fin de línea CRLF.
- `valid` es 1/0; `warnings` une las advertencias con " | ".
- Los nombres de columna son los de TelemetryReading (schema.py).
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


def csv_chunks(
    db: Database, mission_id: int, batch_size: int = BATCH_SIZE
) -> Iterator[str]:
    """Genera el CSV de una misión en bloques de texto (cabecera primero)."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")

    def flush() -> str:
        text = buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)
        return text

    writer.writerow(CSV_COLUMNS)
    yield "\ufeff" + flush()

    after_id = 0
    while True:
        rows = db.fetch_telemetry_batch(mission_id, after_id, batch_size)
        if not rows:
            return
        for row in rows:
            writer.writerow(_format_row(row))
        after_id = rows[-1]["id"]
        yield flush()


def export_filename(mission: dict) -> str:
    """Nombre de archivo seguro: mision_<id>_<nombre-en-ascii>.csv"""
    ascii_name = (
        unicodedata.normalize("NFKD", mission["name"])
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    slug = re.sub(r"[^A-Za-z0-9]+", "-", ascii_name).strip("-").lower()[:40]
    base = f"mision_{mission['id']}"
    return f"{base}_{slug}.csv" if slug else f"{base}.csv"
