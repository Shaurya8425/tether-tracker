# Tether Tracker (Windows)

Track USB tethering data usage per session and keep a running daily total.

## What this project does

- Detects your USB tethering network interface
- Tracks download/upload bytes for each session
- Auto-saves when phone is unplugged
- Supports reconnect and starts a new session automatically
- Writes usage history to `data_log.txt`

## Files you should know

- `track_tethering_v2.py` → main tracker (records sessions)
- `watcher.py` → keeps tracker running and auto-restarts on crash/file changes
- `install.bat` → one-click setup (Task Scheduler auto-start on login)
- `uninstall.bat` → removes scheduled auto-start task
- `migrate_log.py` → one-time migration for old log format

## Requirements

- Windows
- Python 3 (available in PATH as `python`)
- Internet once for first install (`psutil` is installed by `install.bat`)

## Quick start (recommended)

1. Open Command Prompt **as Administrator**.
2. Go to this project folder:
   ```bat
   cd /d C:\Users\amany\tether-tracker
   ```
3. Run installer:
   ```bat
   install.bat
   ```
4. Done. Tracker is now configured to start at every Windows login.

## Start manually (without installer)

From project folder, run:

```bat
python watcher.py
```

This starts the tracker and writes:

- watcher events to `watcher_log.txt`
- tracker console output to `tracker_output.txt`
- usage records to `data_log.txt`

## Migrate old logs (only if needed)

If your old `data_log.txt` was created by an older tracker version:

```bat
python migrate_log.py
```

- Creates backup: `data_log_backup.txt`
- Rewrites entries to include `Session:` and `Day Total:` fields

## Uninstall auto-start

Run:

```bat
uninstall.bat
```

This removes the scheduled task but keeps your `data_log.txt`.

## Notes

- Use USB tethering from your phone and keep it enabled.
- Unplugging phone auto-saves the current session.
- Press `Ctrl + C` in manual mode to save and exit.

## Troubleshooting

- **`python` not found**: install Python 3 and enable “Add Python to PATH”.
- **No data tracked**: verify USB tethering is ON and Windows detects the adapter.
- **No auto-start after login**: re-run `install.bat` as Administrator.

## GitHub safety

Do not commit runtime/private files. This repo already includes a `.gitignore` for:

- `data_log.txt`, `data_log_backup.txt`
- `watcher_log.txt`, `tracker_output.txt`
- `.checkpoint.tmp`
- virtual env/cache/editor files
