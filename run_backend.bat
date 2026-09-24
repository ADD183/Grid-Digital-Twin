@echo off
echo Starting Renewable Grid Digital Twin API on http://127.0.0.1:8000 ...
call .venv\Scripts\activate.bat
python -m uvicorn api:app --host 127.0.0.1 --port 8000 --reload
