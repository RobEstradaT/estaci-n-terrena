"""
Renumera el repositorio al esquema único de prototipos (1 a 9).

Correspondencia:
    Incremento 1..6          -> Prototipo 1..6
    Prototipo 1 (histórico)  -> Prototipo 7
    Prototipo 2 (alertas)    -> Prototipo 8
    Prototipo 3 (pruebas)    -> Prototipo 9

Uso (desde la raíz del repositorio, con Git limpio para poder revisar el diff):
    python renumerar_repositorio.py --dry-run   # solo muestra qué archivos cambiaría
    python renumerar_repositorio.py             # aplica los cambios

Solo toca comentarios, docstrings y documentación (no lógica). Se niega a correr
dos veces (crea el archivo .renumeracion_prototipos) porque los números 1-3
cambiarían otra vez. Los archivos DEVELOPMENT_PLAN.md y REGLAS_ESTACION_TERRENA.md
se reemplazan con las versiones nuevas; aquí se omiten.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MARKER = ROOT / ".renumeracion_prototipos"
EXTENSIONS = {".py", ".js", ".jsx", ".css", ".md", ".ino", ".html"}
SKIP_DIRS = {"node_modules", "venv", ".venv", ".git", "dist", "data", "__pycache__"}
SKIP_FILES = {"DEVELOPMENT_PLAN.md", "REGLAS_ESTACION_TERRENA.md", "package-lock.json"}
OBSOLETE = ["docs/DEVELOPMENT_PLAN_actualizado.md"]

README_STATUS = """## Estado

| Prototipo | Estado |
|---|---|
| 1 Fuente simulada y procesamiento | Completado |
| 2 FastAPI + WebSocket | Completado |
| 3 Dashboard | Completado |
| 4 Gráficas en vivo | Completado |
| 5 UART real (`SerialESP32`) | Implementado; falta la prueba con el ESP32 físico |
| 6 Persistencia en SQLite + exportación CSV y JSON | Completado |
| 7 Análisis histórico | Implementado; pendiente de evaluación |
| 8 Alertas y diagnóstico | Implementado; pendiente de evaluación |
| 9 Pruebas finales y refinamiento | Pendiente |

"""

# Reemplazos de texto exacto (se aplican primero, antes de la renumeración general).
LITERAL = [
    # main.py (docstring)
    ("- Desarrollo previo: fuente simulada o serial, WebSocket, misiones y CSV\n  (Incrementos 1, 2, 5 y 6).",
     "- Prototipos 1, 2, 5 y 6: fuente simulada o serial, WebSocket, misiones y\n  exportación CSV y JSON."),
    # README.md
    ("La alerta de pérdida de señal está prevista en el Prototipo 2.",
     "La pérdida de señal del CanSat se indica con el indicador \"TRAMAS\" del encabezado y en el panel de alertas (Prototipo 8)."),
    ("- **Pérdida de enlace y alertas dedicadas:** Prototipo 2.",
     "- **Umbrales de alertas:** provisionales hasta confirmar los parámetros LoRa y la frecuencia de transmisión (ver `docs/ALERTS.md`)."),
    # PROJECT_CONTEXT.md, sección 8
    ("El proyecto se desarrollará incrementalmente.",
     "El proyecto se desarrolla mediante prototipado: cada prototipo es una versión funcional y demostrable del sistema."),
    ("Cada incremento debe producir una parte funcional y comprobable del sistema.",
     "Cada prototipo debe producir una parte funcional y comprobable del sistema, con un objetivo y criterios de evaluación definidos antes de implementarse."),
    ("No avanzar automáticamente al siguiente incremento.",
     "No avanzar automáticamente al siguiente prototipo."),
    ("Cada incremento debe:", "Cada prototipo debe:"),
]


def renumber(text: str, is_readme: bool) -> str:
    if is_readme:
        text = re.sub(r"## Estado\n.*?(?=El avance y los criterios)", README_STATUS, text, flags=re.S)
    for old, new in LITERAL:
        text = text.replace(old, new)
    # Prototipos antiguos 1-3 -> 7-9 (con marcador para no volver a procesarlos).
    text = re.sub(r"\bPrototipo (\d)\b", lambda m: f"§P{int(m.group(1)) + 6}" if m.group(1) in "123" else m.group(0), text)
    text = re.sub(r"\bPrototipos (\d) y (\d)\b", lambda m: f"§Ps{int(m.group(1)) + 6} y {int(m.group(2)) + 6}", text)
    # Incrementos -> Prototipos (mismo número).
    text = re.sub(r"\bIncremento(s?)\b", r"Prototipo\1", text)
    text = re.sub(r"\bincremento(s?)\b", r"prototipo\1", text)
    text = text.replace("§Ps", "Prototipos ").replace("§P", "Prototipo ")
    return text


def main() -> int:
    dry = "--dry-run" in sys.argv
    if MARKER.exists():
        print("Ya se aplicó antes (existe .renumeracion_prototipos). No se hace nada.")
        return 1
    changed = []
    for path in sorted(ROOT.rglob("*")):
        if (not path.is_file() or path == Path(__file__).resolve() or path.suffix not in EXTENSIONS
                or path.name in SKIP_FILES
                or any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts)):
            continue
        original = path.read_text(encoding="utf-8")
        updated = renumber(original, path.name == "README.md")
        if updated != original:
            changed.append(path.relative_to(ROOT))
            if not dry:
                path.write_text(updated, encoding="utf-8", newline="")
    for rel in OBSOLETE:
        target = ROOT / rel
        if target.exists():
            changed.append(Path(rel + "  (se elimina)"))
            if not dry:
                target.unlink()
    print(("Cambiaría" if dry else "Actualizados"), len(changed), "archivos:")
    for rel in changed:
        print("  -", rel)
    if not dry:
        MARKER.write_text("renumeración aplicada\n", encoding="utf-8")
        print("\nRevisa con `git diff`. Verifica que no queden restos con:")
        print('  git grep -n -i "incremento"')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
