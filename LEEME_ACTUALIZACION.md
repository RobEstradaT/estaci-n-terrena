# Actualización: Prototipo 8 — Alertas y diagnóstico

Descomprime el zip **encima de la raíz del repositorio** (conserva las rutas) y reemplaza los archivos.

## Archivos

Nuevos:
- `backend/app/alerts.py`
- `backend/tests/test_alerts.py`
- `frontend/src/components/AlertPanel.jsx`, `AlertPanel.css`
- `docs/ALERTS.md`

Modificados (reemplazar):
- `backend/app/main.py`
- `backend/app/telemetry/source.py`, `processor.py`, `serial_esp32.py`
- `frontend/src/App.jsx`, `hooks/useTelemetrySocket.js`, `components/MissionHeader.jsx`
- `docs/ARCHITECTURE.md`, `docs/DEVELOPMENT_PLAN.md`, `README.md`
- `REGLAS_ESTACION_TERRENA.md` (si lo tienes en otra carpeta, cópialo allí)

## Verificar (PowerShell)

```powershell
cd backend
venv\Scripts\Activate.ps1
python -m unittest discover -s tests -v      # deben pasar todas, incluidas test_alerts.py
uvicorn app.main:app --port 8000
# otra terminal:
cd frontend
npm run dev
```

## Subir a GitHub

```powershell
git status
git rm docs/DEVELOPMENT_PLAN_actualizado.md   # solo si todavía existe
git add backend frontend docs README.md REGLAS_ESTACION_TERRENA.md
git commit -m "Prototipo 8: alertas y diagnóstico (señal débil, pérdida de enlace, datos inválidos, errores seriales)"
git push
```
