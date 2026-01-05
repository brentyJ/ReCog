@echo off
REM ReCog Dashboard Launcher
cd /d "%~dp0"
echo Starting ReCog Dashboard...
echo.
echo Dashboard: http://localhost:3101
echo Backend:   http://localhost:5100
echo.
npm run dev
