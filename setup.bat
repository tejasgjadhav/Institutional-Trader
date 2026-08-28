@echo off
REM Setup for Windows. Creates the venv, installs requirements, seeds .env.
REM Study code. Not investment advice. Read DISCLAIMER.md before running anything.
setlocal
cd /d "%~dp0"
echo ==^> Creating virtualenv
python -m venv .venv || goto :err
echo ==^> Installing dependencies
.venv\Scripts\python -m pip install -q --upgrade pip
.venv\Scripts\python -m pip install -q -r requirements.txt || goto :err
if not exist .env copy .env.example .env >nul && echo ==^> Created .env - edit it and add your UPSTOX_ANALYTICS_TOKEN
if not exist data mkdir data
if not exist logs mkdir logs
echo.
echo Done.
echo   Run one cycle:  .venv\Scripts\python -m engine.engine_runner --once
echo   Run the engine: run_engine.bat
echo   Open the app:   run_viewer.bat
echo.
echo Read DISCLAIMER.md. The strategies that ship have been tested and they lose money.
goto :eof
:err
echo Setup failed. Is Python 3.9+ on your PATH?
exit /b 1
