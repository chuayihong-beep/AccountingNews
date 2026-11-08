@echo off
rem Run one job right now.  Usage:  run-now.bat collect | brief | send
cd /d "%~dp0\.."
call local-runner\.venv\Scripts\activate.bat
if "%1"=="" (echo Usage: run-now.bat collect ^| brief ^| send & pause & exit /b 1)
python -m collector.local_runner --once %1
pause
