@echo off
:: Removes TetherTracker from Task Scheduler and kills running process
set TASK_NAME=TetherTracker

schtasks /end /tn "%TASK_NAME%" >nul 2>&1
schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1
taskkill /f /im python.exe /fi "WINDOWTITLE eq TetherTracker" >nul 2>&1

echo  Tether Tracker uninstalled.
echo  Your data_log.txt is preserved.
pause
