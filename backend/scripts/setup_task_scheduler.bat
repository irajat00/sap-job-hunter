@echo off
REM setup_task_scheduler.bat
REM Registers a Windows Task Scheduler task that runs run_collector.bat
REM every 15 minutes. Run this ONCE, as Administrator (right-click ->
REM "Run as administrator"), from anywhere.
REM
REM To remove it later: schtasks /Delete /TN "SAP_PP_QM_Job_Collector" /F

set SCRIPT_DIR=%~dp0
set TASK_NAME=SAP_PP_QM_Job_Collector

schtasks /Create /TN "%TASK_NAME%" ^
    /TR "\"%SCRIPT_DIR%run_collector.bat\"" ^
    /SC MINUTE /MO 15 ^
    /RL LIMITED ^
    /F

echo.
echo Task "%TASK_NAME%" registered to run every 15 minutes.
echo View/edit it any time in Task Scheduler, or run:
echo     schtasks /Query /TN "%TASK_NAME%"
echo To remove it:
echo     schtasks /Delete /TN "%TASK_NAME%" /F
pause
