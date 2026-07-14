@echo off
REM ============================================================================
REM  Institutional Trader — one-shot setup from a fresh clone (WINDOWS).
REM    git clone https://github.com/tejasgjadhav/Institutional-Trader.git
REM    cd Institutional-Trader
REM    setup.bat
REM  Creates the venv, installs deps, seeds .env, makes data/ + logs/.
REM  Windows has no launchd, so you start the two processes yourself with the
REM  run_engine.bat / run_viewer.bat scripts this creates (see the end).
REM  Requires Python 3.9+ on PATH (python.org installer, "Add to PATH" ticked).
REM ============================================================================
setlocal
cd /d "%~dp0"

echo ==^> Repo: %CD%

REM 1) Python present?
where python >nul 2>&1
if errorlevel 1 (
  echo ERROR: Python not found on PATH. Install Python 3.9+ from https://python.org
  echo        and tick "Add python.exe to PATH" during install, then re-run setup.bat.
  exit /b 1
)

REM 2) venv + dependencies
if not exist ".venv\Scripts\python.exe" (
  echo ==^> Creating virtualenv (.venv)
  python -m venv .venv
)
echo ==^> Installing dependencies
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo ERROR: dependency install failed. See the pip output above.
  exit /b 1
)

REM 3) .env from template (never overwrite an existing one)
if not exist ".env" (
  copy ".env.example" ".env" >nul
  echo ==^> Created .env from template — EDIT IT and add your UPSTOX_ANALYTICS_TOKEN.
)
if not exist "data" mkdir data
if not exist "logs" mkdir logs

echo.
echo ============================================================================
echo  Setup done.
echo  1) Open .env in Notepad and add your UPSTOX_ANALYTICS_TOKEN (free, read-only).
echo     Optional: TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID for phone alerts.
echo  2) Start the ENGINE  (leave it running, minimised):  run_engine.bat
echo  3) Start the VIEWER  (the dashboard):                run_viewer.bat
echo  The engine must be running for the dashboard to show live data.
echo ============================================================================
endlocal
