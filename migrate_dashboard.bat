@echo off
REM Migrate new React UI to ReCog dashboard

cd /d "%~dp0"
echo.
echo ====================================================================
echo   RECOG DASHBOARD MIGRATION
echo ====================================================================
echo.
echo This will replace the old dashboard with the new React UI
echo from C:\EhkoDev\recog-ui
echo.
pause
echo.

python migrate_dashboard.py

echo.
pause
