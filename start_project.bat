@echo off
echo Starting MemeGuard Backend and Frontend...

:: Start Backend in a new window
start "MemeGuard Backend" cmd /k "cd /d "%~dp0backend" && set PYTHONUTF8=1&& .venv\Scripts\python -m uvicorn app.main:app --reload --port 8000"

:: Start Frontend in a new window
start "MemeGuard Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"

echo Both servers are starting!
echo Backend API will be at: http://localhost:8000
echo Frontend UI will be at: http://localhost:5173
pause
