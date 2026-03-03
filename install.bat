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

:: -- Install psutil ------------------------------------------
echo Installing psutil...
%PYTHON% -m pip install psutil --quiet

:: -- Remove old task if exists --------------------------------
schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1

:: -- Create Task Scheduler entry ------------------------------
:: Runs at login, hidden, with highest privileges
schtasks /create ^
  /tn "%TASK_NAME%" ^
  /tr "\"%PYTHON%\" \"%WATCHER%\"" ^
  /sc ONLOGON ^
  /rl HIGHEST ^
  /f ^
  /it >nul

if errorlevel 1 (
    echo [ERROR] Failed to create scheduled task.
    echo Try running this batch file as Administrator.
    pause & exit /b 1
)

echo.
echo  ============================================================
echo   Tether Tracker installed successfully!
echo  ============================================================
echo   - Starts automatically every time you log into Windows
echo   - Runs silently in background (no window)
echo   - Edit track_tethering_v2.py anytime, changes apply instantly
echo   - Check watcher_log.txt to see watcher activity
echo   - Check tracker_output.txt to see tracker live output
echo   - Check data_log.txt for your usage history
echo.
echo   Folder: %FOLDER%
echo  ============================================================
echo.

:: -- Start it right now without rebooting ---------------------
start "" /B %PYTHON% "%WATCHER%"
echo   Started now in background. You are being tracked!
echo.
pause
