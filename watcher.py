import subprocess
import time
import os
import sys
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TRACKER    = os.path.join(SCRIPT_DIR, "track_tethering_v2.py")
WLOG_FILE  = os.path.join(SCRIPT_DIR, "watcher_log.txt")
OUT_FILE   = os.path.join(SCRIPT_DIR, "tracker_output.txt")
INTERVAL   = 3
PY         = sys.executable


def wlog(msg):
    ts   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = "[" + ts + "]  " + msg
    print(line, flush=True)
    with open(WLOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def mtime(p):
    try:
        return os.path.getmtime(p)
    except Exception:
        return 0


def start():
    try:
        out_f = open(OUT_FILE, "a", encoding="utf-8")
        p = subprocess.Popen(
            [PY, TRACKER],
            stdout=out_f,
            stderr=subprocess.STDOUT,
            creationflags=0x08000000
        )
        wlog("Tracker started PID=" + str(p.pid))
        return p
    except Exception as e:
        wlog("Start error: " + str(e))
        return None


def stop(p):
    if p and p.poll() is None:
        try:
            p.terminate()
            p.wait(timeout=5)
        except Exception:
            p.kill()
        wlog("Tracker stopped")


def main():
    wlog("=" * 40)
    wlog("Watcher started")
    wlog("Watching: " + TRACKER)
    wlog("Python: " + PY)
    wlog("=" * 40)

    if not os.path.exists(TRACKER):
        wlog("ERROR: tracker script not found at " + TRACKER)
        return

    proc = start()
    last = mtime(TRACKER)

    while True:
        time.sleep(INTERVAL)

        # Tracker crashed -> restart
        if proc and proc.poll() is not None:
            wlog("Tracker exited (code " + str(proc.returncode) + "). Restarting in 3s...")
            time.sleep(3)
            proc = start()
            last = mtime(TRACKER)
            continue

        # File edited -> hot-reload
        cur = mtime(TRACKER)
        if cur != last:
            time.sleep(1)
            cur = mtime(TRACKER)
            if cur != last:
                wlog("File change detected -> reloading tracker...")
                stop(proc)
                time.sleep(1)
                proc = start()
                last = cur


if __name__ == "__main__":
    main()