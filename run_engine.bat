@echo off
REM Institutional Trader — headless ENGINE (Windows). Keep this window open (minimise it).
REM This is the process that scans, fires signals, resolves paper trades, and sends alerts.
REM It must be running for the dashboard to show live data. Ctrl+C to stop.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo ERROR: .venv not found. Run setup.bat first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m engine.engine_runner
pause
