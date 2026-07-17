@echo off
REM ============================================================================
REM  Institutional Trader — Windows auto-start (the launchd equivalent).
REM    autostart_windows.bat          registers the engine to start 08:55
REM                                   every weekday via Task Scheduler
REM    autostart_windows.bat remove   removes the scheduled task again
REM  The engine idles outside market hours, so an early start is harmless.
REM  The task runs when you are logged in; keep the PC on (or waking) by 08:55.
REM ============================================================================
setlocal
cd /d "%~dp0"

if /I "%~1"=="remove" (
  schtasks /delete /tn "InstitutionalTrader Engine" /f
  echo ==^> Auto-start removed.
  exit /b 0
)

schtasks /create /tn "InstitutionalTrader Engine" ^
  /tr "\"%~dp0run_engine.bat\" scheduled" ^
  /sc weekly /d MON,TUE,WED,THU,FRI /st 08:55 /f
if errorlevel 1 (
  echo ERROR: could not create the scheduled task. Try from an elevated prompt.
  exit /b 1
)
echo.
echo ==^> Done. The engine will start 08:55 every weekday.
echo     Check it:   schtasks /query /tn "InstitutionalTrader Engine"
echo     Remove it:  autostart_windows.bat remove
endlocal
