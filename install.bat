@echo off
:: ============================================================
::  Tether Tracker - One-Click Installer
::  Run this ONCE as Administrator to set everything up
:: ============================================================
setlocal

:: -- Config ---------------------------------------------------
set TASK_NAME=TetherTracker
set FOLDER=C:\Users\amany\tether-tracker\
set WATCHER=%FOLDER%watcher.py
set PYTHON=python

:: -- Check Python ---------------------------------------------
%PYTHON% --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Make sure Python is in PATH.
    pause & exit /b 1
)

:: -- Install psutil -------------------------------------------
echo Installing psutil...
%PYTHON% -m pip install psutil --quiet

:: -- Remove old tasks if exist --------------------------------
schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1
schtasks /delete /tn "%TASK_NAME%_wake" /f >nul 2>&1
schtasks /delete /tn "%TASK_NAME%_watchdog" /f >nul 2>&1

:: -- Task 1: Runs at login, hidden, with highest privileges ---
schtasks /create ^
  /tn "%TASK_NAME%" ^
  /tr "\"%PYTHON%\" \"%WATCHER%\"" ^
  /sc ONLOGON ^
  /rl HIGHEST ^
  /f ^
  /it >nul

if errorlevel 1 (
    echo [ERROR] Failed to create login task.
    echo Try running this batch file as Administrator.
    pause & exit /b 1
)

:: -- Task 2: Restarts watcher when laptop wakes from sleep ----
schtasks /create ^
  /tn "%TASK_NAME%_wake" ^
  /tr "\"%PYTHON%\" \"%WATCHER%\"" ^
  /sc ONEVENT ^
  /ec System ^
  /mo "*[System[Provider[@Name='Microsoft-Windows-Power-Troubleshooter'] and EventID=1]]" ^
  /rl HIGHEST ^
  /f ^
  /it >nul

:: -- Task 3: Hourly watchdog in case watcher dies/zombie ------
schtasks /create ^
  /tn "%TASK_NAME%_watchdog" ^
  /tr "\"%PYTHON%\" \"%WATCHER%\"" ^
  /sc HOURLY ^
  /rl HIGHEST ^
  /f ^
  /it >nul

echo.
echo  ============================================================
echo   Tether Tracker installed successfully!
echo  ============================================================
echo   - Starts automatically every time you log into Windows
echo   - Restarts automatically when laptop wakes from sleep
echo   - Hourly watchdog revives it if it ever dies
echo   - Runs silently in background (no window)
echo   - Edit track_tethering_v2.py anytime, changes apply instantly
echo   - Check watcher_log.txt to see watcher activity
echo   - Check tracker_output.txt to see tracker live output
echo   - Check data_log.txt for your usage history
echo.
echo   Folder: %FOLDER%
echo  ============================================================
echo.

:: -- Gracefully save current session before restarting --------
echo. > "%FOLDER%.shutdown"
timeout /t 3 /nobreak >nul
taskkill /f /im python.exe >nul 2>&1
timeout /t 1 /nobreak >nul
start "" /B %PYTHON% "%WATCHER%"
echo   Started now in background. You are being tracked!
echo.
pause