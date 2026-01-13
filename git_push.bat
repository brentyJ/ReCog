@echo off
REM Quick ReCog Git Push
REM Run from ReCog directory
REM Now with preflight checks for quality assurance

cd /d "%~dp0"

echo.
echo Running preflight checks...
echo.
python _scripts\preflight_check.py
if %errorlevel% neq 0 (
    echo.
    echo Preflight checks FAILED. Fix issues before pushing.
    echo.
    pause
    exit /b 1
)

echo.
echo Preflight passed - proceeding with git push...
echo.

python git_push.py
pause
