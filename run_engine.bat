@echo off
REM Institutional Trader — headless ENGINE (Windows). Keep this window open (minimise it).
REM This is the process that scans, fires signals, resolves paper trades, and sends alerts.
REM It must be running for the dashboard to show live data. Ctrl+C to stop.
cd /d "%~dp0"
REM Don't start a second engine if one is already running (matters for the
REM scheduled 08:55 start — see autostart_windows.bat).
powershell -NoProfile -Command "if (Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -match 'engine.engine_runner' }) { exit 1 }" >nul 2>&1
if errorlevel 1 (
  echo Engine is already running — nothing to do.
  if /I not "%~1"=="scheduled" pause
  exit /b 0
)
if not exist ".venv\Scripts\python.exe" (
  echo ERROR: .venv not found. Run setup.bat first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m engine.engine_runner
pause
