@echo off
title AulaAI - Spanish Learning System
echo.
echo ============================================================
echo   AulaAI - Spanish Learning System
echo   Starting server...
echo ============================================================
echo.

cd /d "%~dp0"

:: Start the server
start "" "http://localhost:3000"
python server.py

pause
