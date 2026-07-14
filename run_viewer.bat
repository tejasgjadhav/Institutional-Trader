@echo off
REM Institutional Trader — read-only DASHBOARD (Windows). Safe to open/close anytime;
REM it only displays what the engine wrote and never places orders. Start the engine first
REM (run_engine.bat). Close this window to close the dashboard.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo ERROR: .venv not found. Run setup.bat first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" main.py
pause
