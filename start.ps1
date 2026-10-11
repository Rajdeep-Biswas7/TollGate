# PowerShell start script for Tollgate services
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "Starting Tollgate Services..." -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

$scriptDir = $PSScriptRoot

Write-Host "Starting AI Service (Port 8000)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$scriptDir\ai'; .\.venv\Scripts\uvicorn.exe app.main:app --port 8000"

Write-Host "Starting Backend Service (Port 4000)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$scriptDir\backend'; npm start"

Write-Host "Starting Frontend Service (Port 3000)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$scriptDir\frontend'; npm run dev"

Write-Host "========================================================" -ForegroundColor Green
Write-Host "All services launched!" -ForegroundColor Green
Write-Host "- Web UI:  http://localhost:3000" -ForegroundColor White
Write-Host "- Backend: http://localhost:4000" -ForegroundColor White
Write-Host "- AI API:  http://localhost:8000" -ForegroundColor White
Write-Host "========================================================" -ForegroundColor Green
