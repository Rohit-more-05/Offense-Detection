@echo off
echo Starting MemeGuard Backend...
set PYTHONUTF8=1
call .\.venv\Scripts\Activate.bat
python -m uvicorn app.main:app --reload --port 8000
