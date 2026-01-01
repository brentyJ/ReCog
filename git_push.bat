@echo off
REM Quick ReCog Git Push
REM Run from ReCog directory

cd /d "%~dp0"
python git_push.py
pause
