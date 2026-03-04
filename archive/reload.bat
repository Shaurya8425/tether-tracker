@echo off
:: reload.bat
:: Triggers watcher to reload track_tethering_v2.py immediately
:: No reinstall needed. Just double-click this after editing the tracker.

echo. > "%~dp0.reload"
echo Reload triggered! Watcher will restart tracker within 3 seconds.
echo Check watcher_log.txt to confirm.
timeout /t 3 /nobreak >nul
type "%~dp0watcher_log.txt" | findstr /C:"Tracker started" | findstr /V "findstr"