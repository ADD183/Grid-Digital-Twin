@echo off
echo Starting Renewable Grid Digital Twin (Backend + Frontend)...
start "Grid Twin - Backend API" cmd /k "call .venv\Scripts\activate.bat && python -m uvicorn api:app --host 127.0.0.1 --port 8000 --reload"
start "Grid Twin - Frontend React SPA" cmd /k "cd frontend && npm run dev"
echo Services are starting in separate terminal windows:
echo - Backend API:  http://127.0.0.1:8000
echo - Frontend SPA: http://localhost:5173
