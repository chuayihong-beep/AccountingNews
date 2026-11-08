@echo off
rem Start the scheduler. Leave this window open (minimise it). It restarts itself if it ever stops.
cd /d "%~dp0\.."
call local-runner\.venv\Scripts\activate.bat
:again
python -m collector.local_runner
echo Runner stopped. Restarting in 30 seconds (close this window to stop).
timeout /t 30 /nobreak >nul
goto again
