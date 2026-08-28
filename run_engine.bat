@echo off
REM Runs the engine. Leave this window open.
cd /d "%~dp0"
.venv\Scripts\python -m engine.engine_runner
