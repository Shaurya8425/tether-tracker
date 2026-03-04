"""
USB Tethering Data Tracker v3.2
================================
- Polls .shutdown flag for graceful save before hot-reload
- Writes live_status.tmp every second for view_stats.py
- Logs every session to data_log.txt on unplug/reload/exit
"""

import psutil
import time
import os
import re
import sys
from datetime import datetime

# --- CONFIG ------------------------------------------------------------------
BASE_DIR        = os.path.dirname(os.path.abspath(__file__))
LOG_FILE        = os.path.join(BASE_DIR, "data_log.txt")
LIVE_FILE       = os.path.join(BASE_DIR, "live_status.tmp")
CHECKPOINT_FILE = os.path.join(BASE_DIR, ".checkpoint.tmp")
SHUTDOWN_FLAG   = os.path.join(BASE_DIR, ".shutdown")
POLL_INTERVAL   = 1
CHECKPOINT_SECS = 60
WAIT_TIMEOUT    = 5
TETHER_KEYWORDS = ["rndis", "remote ndis", "android", "usb ethernet", "usb tether", "ethernet 4"]
# -----------------------------------------------------------------------------


def bytes_to_human(n):
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if n < 1024:
            return "{:.3f} {}".format(n, unit)
        n /= 1024
    return "{:.3f} PB".format(n)


def human_to_bytes(s):
    s = s.strip()
    units = {"TB": 1024**4, "GB": 1024**3, "MB": 1024**2, "KB": 1024, "B": 1}
    for unit, factor in units.items():
        if s.endswith(unit):
            try:
                return float(s[:-len(unit)].strip()) * factor
            except ValueError:
                return 0
    return 0


def shutdown_requested():
    return os.path.exists(SHUTDOWN_FLAG)


def clear_shutdown_flag():
    try:
        if os.path.exists(SHUTDOWN_FLAG):
            os.remove(SHUTDOWN_FLAG)
    except Exception:
        pass


def get_todays_logged_bytes():
    """Sum only Session: values — never Day Total: — to avoid double counting."""
    today = datetime.now().strftime("%Y-%m-%d")
    total = 0.0
    if not os.path.exists(LOG_FILE):
        return total
    # Matches:  |  Session: 1.234 MB  |
    pat = re.compile(
        r"^\[" + re.escape(today) + r"\].*\|  Session:\s*([\d\.]+\s*(?:TB|GB|MB|KB|B))\s*\|"
    )
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if not line.startswith("[" + today + "]"):
                continue
            m = pat.search(line)
            if m:
                total += human_to_bytes(m.group(1))
    return total


def log_session(iface, start_time, end_time, recv, sent, reason=""):
    ts       = int((end_time - start_time).total_seconds())
    h, rem   = divmod(ts, 3600)
    m, s     = divmod(rem, 60)
    dur      = "{}h {}m {}s".format(h, m, s) if h else "{}m {}s".format(m, s)
    tag      = "  [{}]".format(reason) if reason else ""
    date_str = start_time.strftime("%Y-%m-%d")
    sess_b   = recv + sent

    # Skip zero-data unless it's a reload (always log reloads)
    if sess_b == 0 and reason != "reloaded":
        return None

    daily = get_todays_logged_bytes()
    cumul = daily + sess_b

    line = "[{}]  {} -> {}  |  Duration: {}  |  Down: {}  Up: {}  |  Session: {}  |  Day Total: {}{}\n".format(
        date_str,
        start_time.strftime("%I:%M:%S %p"),
        end_time.strftime("%I:%M:%S %p"),
        dur,
        bytes_to_human(recv), bytes_to_human(sent),
        bytes_to_human(sess_b),
        bytes_to_human(cumul), tag
    )

    is_new = not os.path.exists(LOG_FILE)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        if is_new:
            f.write("USB Tethering Data Usage Log\n")
            f.write("=" * 130 + "\n")
        f.write(line)
    return line


def write_live_status(iface, start_time, recv, sent, status="connected"):
    elapsed    = (datetime.now() - start_time).total_seconds()
    daily_prev = get_todays_logged_bytes()
    try:
        with open(LIVE_FILE, "w", encoding="utf-8") as f:
            f.write("status={}\n".format(status))
            f.write("iface={}\n".format(iface))
            f.write("start={}\n".format(start_time.strftime("%I:%M:%S %p")))
            f.write("elapsed={:.0f}\n".format(elapsed))
            f.write("recv={}\n".format(recv))
            f.write("sent={}\n".format(sent))
            f.write("daily_prev={}\n".format(daily_prev))
            f.write("updated={}\n".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    except Exception:
        pass


def clear_live_status(status="idle"):
    try:
        with open(LIVE_FILE, "w", encoding="utf-8") as f:
            f.write("status={}\n".format(status))
            f.write("updated={}\n".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    except Exception:
        pass


def checkpoint_session(iface, start_time, recv, sent):
    ts     = int((datetime.now() - start_time).total_seconds())
    h, rem = divmod(ts, 3600)
    m, s   = divmod(rem, 60)
    try:
        with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
            f.write("[CHECKPOINT {}]  Started: {}  |  {}h {}m {}s  |  Session: {}\n".format(
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                start_time.strftime("%I:%M:%S %p"),
                h, m, s, bytes_to_human(recv + sent)
            ))
    except Exception:
        pass


def clear_checkpoint():
    try:
        if os.path.exists(CHECKPOINT_FILE):
            os.remove(CHECKPOINT_FILE)
    except Exception:
        pass


def find_tether_interface():
    try:
        for name, stat in psutil.net_if_stats().items():
            if any(kw in name.lower() for kw in TETHER_KEYWORDS) and stat.isup:
                return name
    except Exception:
        pass
    return None


def is_interface_alive(name):
    try:
        s = psutil.net_if_stats()
        return name in s and s[name].isup
    except Exception:
        return False


def get_interface_bytes(name):
    try:
        c = psutil.net_io_counters(pernic=True)
        if name in c:
            return c[name].bytes_recv, c[name].bytes_sent
    except Exception:
        pass
    return 0, 0


def run_session(iface, session_num):
    start          = datetime.now()
    b_recv, b_sent = get_interface_bytes(iface)
    p_recv, p_sent = b_recv, b_sent
    s_recv, s_sent = 0, 0
    last_cp        = time.time()

    try:
        while True:
            time.sleep(POLL_INTERVAL)

            # Graceful shutdown requested by watcher (hot-reload)
            if shutdown_requested():
                clear_shutdown_flag()
                end = datetime.now()
                log_session(iface, start, end, s_recv, s_sent, reason="reloaded")
                clear_checkpoint()
                clear_live_status("idle")
                sys.exit(0)

            # Phone unplugged
            if not is_interface_alive(iface):
                end = datetime.now()
                log_session(iface, start, end, s_recv, s_sent, reason="unplugged")
                clear_checkpoint()
                clear_live_status("waiting")
                return "unplugged"

            c_recv, c_sent = get_interface_bytes(iface)
            if c_recv < p_recv or c_sent < p_sent:
                b_recv = c_recv - s_recv
                b_sent = c_sent - s_sent

            s_recv = c_recv - b_recv
            s_sent = c_sent - b_sent

            if time.time() - last_cp >= CHECKPOINT_SECS:
                checkpoint_session(iface, start, s_recv, s_sent)
                last_cp = time.time()

            write_live_status(iface, start, s_recv, s_sent)
            p_recv, p_sent = c_recv, c_sent

    except KeyboardInterrupt:
        end = datetime.now()
        log_session(iface, start, end, s_recv, s_sent, reason="manual exit")
        clear_checkpoint()
        clear_live_status("idle")
        return "manual_exit"


def main():
    clear_shutdown_flag()
    clear_live_status("waiting")

    iface = find_tether_interface()
    if not iface:
        while not iface:
            if shutdown_requested():
                clear_shutdown_flag()
                sys.exit(0)
            time.sleep(WAIT_TIMEOUT)
            iface = find_tether_interface()

    n = 0
    while True:
        n += 1
        result = run_session(iface, n)
        if result == "manual_exit":
            break
        clear_live_status("waiting")
        iface = None
        while not iface:
            if shutdown_requested():
                clear_shutdown_flag()
                sys.exit(0)
            time.sleep(WAIT_TIMEOUT)
            iface = find_tether_interface()


if __name__ == "__main__":
    main()