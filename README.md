# Tether Tracker (Windows)

Track USB tethering data usage per session and keep a running daily total.

## Overview

- Detects your USB tethering network interface automatically
- Tracks download/upload bytes for each session
- Auto-saves when phone is unplugged, auto-reconnects on replug
- Live dashboard to view current stats in real-time
- Logs usage history to `data_log.txt`

## Core Components

| File                    | Purpose                                                                     |
| ----------------------- | --------------------------------------------------------------------------- |
| `track_tethering_v2.py` | Main tracker (records sessions, updates live status)                        |
| `watcher.py`            | Supervisor (keeps tracker running, auto-restarts, watches for code changes) |
| `view_stats.py`         | Live dashboard (view current stats anytime)                                 |
| `install.bat`           | One-click setup (auto-start on Windows login)                               |
| `uninstall.bat`         | Removes auto-start task                                                     |

## Requirements

- Windows 10/11
- Python 3 (available in PATH as `python`)
- Internet (first install only, to download `psutil`)

## Installation & Auto-Start

1. Open **Command Prompt as Administrator**
2. Navigate to project folder:
   ```batch
   cd /d C:\Users\amany\tether-tracker
   ```
3. Run installer:
   ```batch
   install.bat
   ```
4. Done! Tracker starts automatically at every Windows login.

## Manual Start (without auto-start)

```batch
python watcher.py
```

Generates:

- `watcher_log.txt` — watcher events
- `tracker_output.txt` — tracker console output
- `data_log.txt` — usage history
- `live_status.tmp` — live stats (deleted on exit)

## Live Dashboard

While tracker is running, view real-time stats anytime:

```batch
python view_stats.py
```

Press `Ctrl + C` to close. **Background tracker keeps running.**

## How It Works

1. **Watcher** starts and launches **Tracker**
2. **Tracker** detects USB tether interface and polls every 1 second
3. When connected: logs each session on-demand; updates `live_status.tmp` every second for the dashboard
4. When unplugged: auto-saves session and waits for reconnect
5. **Watcher** auto-reloads if you edit `track_tethering_v2.py` (saves current session first)

## Uninstall

```batch
uninstall.bat
```

Removes auto-start task. Your `data_log.txt` is kept.

## Tips

- USB tethering must be enabled on your phone
- Unplugging auto-saves the current session
- Press `Ctrl + C` in manual mode to save and exit gracefully
- Edit `track_tethering_v2.py` anytime—watcher auto-reloads without losing data

## Troubleshooting

| Problem                   | Solution                                                   |
| ------------------------- | ---------------------------------------------------------- |
| `python` not found        | Install Python 3 and enable "Add Python to PATH"           |
| No data being tracked     | Verify USB tethering is ON and Windows detects the adapter |
| No auto-start after login | Run `install.bat` as Administrator again                   |
