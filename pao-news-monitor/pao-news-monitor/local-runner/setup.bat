@echo off
rem One-time setup. Double-click this file.
cd /d "%~dp0\.."
where python >nul 2>nul
if errorlevel 1 (
  echo Python is not installed. Get Python 3.12 from https://www.python.org/downloads/ and tick "Add python.exe to PATH" in the installer, then run this again.
  pause
  exit /b 1
)
if not exist local-runner\.venv python -m venv local-runner\.venv
call local-runner\.venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m playwright install chromium
if not exist local-runner\.env (
  copy local-runner\.env.example local-runner\.env >nul
  echo.
  echo Created local-runner\.env - opening it. Fill in the keys, save, close it.
  notepad local-runner\.env
)
python -m collector.local_runner --check
echo.
echo If it says "Check passed", setup is done. Next: double-click run.bat
pause
