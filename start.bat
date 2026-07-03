@echo off
title AI Learning Assistant

echo ========================================
echo   Starting AI Learning Assistant...
echo ========================================
echo.

set ROOT=%~dp0

echo [1/2] Starting backend...
start "Backend" cmd /c "cd /d "%ROOT%backend" && .venv\Scripts\uvicorn main:app --reload --host 127.0.0.1 --port 8000"

timeout /t 3 /nobreak >nul

echo [2/2] Starting frontend...
start "Frontend" cmd /c "cd /d "%ROOT%frontend" && npm run dev"

timeout /t 5 /nobreak >nul

echo Opening browser...
start "" "http://127.0.0.1:5173/"

echo.
echo Done!
echo Backend: http://127.0.0.1:8000
echo Frontend: http://127.0.0.1:5173/
echo Close all windows to stop.
echo.
pause
