@echo off
REM run_collector.bat
REM Runs the job collector once. Point Windows Task Scheduler at this file.
REM
REM Edit VENV_PATH and PROJECT_DIR below to match your setup.

set PROJECT_DIR=%~dp0..
set VENV_PATH=%PROJECT_DIR%\venv

cd /d "%PROJECT_DIR%"
call "%VENV_PATH%\Scripts\activate.bat"
python -m collectors.runner >> logs\collector.log 2>&1
