@echo off
echo ========================================================
echo Starting Tollgate Services...
echo ========================================================

set SCRIPT_DIR=%~dp0

echo Starting AI Service (Port 8000)...
start "Tollgate AI Service (:8000)" cmd /k "cd /d %SCRIPT_DIR%ai && .venv\Scripts\uvicorn.exe app.main:app --port 8000"

echo Starting Backend Service (Port 4000)...
start "Tollgate Backend (:4000)" cmd /k "cd /d %SCRIPT_DIR%backend && npm start"

echo Starting Frontend Service (Port 3000)...
start "Tollgate Frontend (:3000)" cmd /k "cd /d %SCRIPT_DIR%frontend && npm run dev"

echo ========================================================
echo All services launched!
echo - Web UI:  http://localhost:3000
echo - Backend: http://localhost:4000
echo - AI API:  http://localhost:8000
echo ========================================================
