@echo off
title AulaAI - Universal Language Platform
echo.
echo ============================================================
echo   AulaAI - Universal Language Platform
echo   Starting server...
echo ============================================================
echo.

cd /d "%~dp0"

:: Start the server
start "" "http://localhost:3000"
python server.py

pause
