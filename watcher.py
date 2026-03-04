import subprocess
import time
import os
import sys
import hashlib
from datetime import datetime

SCRIPT_DIR    = os.path.dirname(os.path.abspath(__file__))
TRACKER       = os.path.join(SCRIPT_DIR, "track_tethering_v2.py")
WLOG_FILE     = os.path.join(SCRIPT_DIR, "watcher_log.txt")
OUT_FILE      = os.path.join(SCRIPT_DIR, "tracker_output.txt")
SHUTDOWN_FLAG = os.path.join(SCRIPT_DIR, ".shutdown")
RELOAD_FLAG   = os.path.join(SCRIPT_DIR, ".reload")
INTERVAL      = 2
SHUTDOWN_WAIT = 6   # seconds to wait for tracker to save & exit cleanly
PY            = sys.executable


def wlog(msg):
    ts   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = "[" + ts + "]  " + msg
    print(line, flush=True)
    with open(WLOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def get_hash(path):
    try:
        with open(path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()
    except Exception:
        return None


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


def graceful_stop(p):
    """
    Ask tracker to save its session and exit cleanly by
    dropping a .shutdown flag file it polls every second.
    Falls back to force-kill if it doesn't exit in time.
    """
    if not p or p.poll() is not None:
        return

    wlog("Requesting graceful shutdown...")

    # Drop the flag — tracker will see it within 1 second
    try:
        open(SHUTDOWN_FLAG, "w").close()
    except Exception:
        pass

    # Wait for tracker to save and exit on its own
    deadline = time.time() + SHUTDOWN_WAIT
    while time.time() < deadline:
        if p.poll() is not None:
            wlog("Tracker exited cleanly (session saved)")
            return
        time.sleep(0.3)

    # Timeout — force kill
    wlog("Tracker did not exit in time, force killing...")
    try:
        p.terminate()
        p.wait(timeout=3)
    except Exception:
        p.kill()

    # Clean up leftover flag just in case
    try:
        if os.path.exists(SHUTDOWN_FLAG):
            os.remove(SHUTDOWN_FLAG)
    except Exception:
        pass


def main():
    wlog("=" * 40)
    wlog("Watcher v3 started (graceful reload)")
    wlog("Watching: " + TRACKER)
    wlog("=" * 40)

    if not os.path.exists(TRACKER):
        wlog("ERROR: tracker not found: " + TRACKER)
        return

    proc      = start()
    last_hash = get_hash(TRACKER)

    while True:
        time.sleep(INTERVAL)

        # Manual reload flag
        if os.path.exists(RELOAD_FLAG):
            wlog("Manual reload triggered")
            try:
                os.remove(RELOAD_FLAG)
            except Exception:
                pass
            graceful_stop(proc)
            time.sleep(1)
            proc      = start()
            last_hash = get_hash(TRACKER)
            continue

        # Tracker crashed -> restart
        if proc and proc.poll() is not None:
            wlog("Tracker exited (code " + str(proc.returncode) + "). Restarting in 3s...")
            time.sleep(3)
            proc      = start()
            last_hash = get_hash(TRACKER)
            continue

        # File content changed -> graceful reload
        cur_hash = get_hash(TRACKER)
        if cur_hash and cur_hash != last_hash:
            wlog("File changed -> graceful reload (saving current session first)...")
            graceful_stop(proc)
            time.sleep(1)
            proc      = start()
            last_hash = cur_hash


if __name__ == "__main__":
    main()