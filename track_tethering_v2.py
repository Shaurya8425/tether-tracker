"""
USB Tethering Data Tracker v3.3
================================
- Splits sessions at midnight -> correct daily totals
- Polls .shutdown flag for graceful save before hot-reload
- Writes live_status.tmp every second for view_stats.py
- Logs every session to data_log.txt on unplug/reload/exit
"""

import psutil
import time
import os
import re
import sys
from datetime import datetime, timedelta

# --- CONFIG ------------------------------------------------------------------
BASE_DIR        = os.path.dirname(os.path.abspath(__file__))
LOG_FILE        = os.path.join(BASE_DIR, "data_log.txt")
LIVE_FILE       = os.path.join(BASE_DIR, "live_status.tmp")
CHECKPOINT_FILE = os.path.join(BASE_DIR, ".checkpoint.tmp")
SHUTDOWN_FLAG   = os.path.join(BASE_DIR, ".shutdown")
POLL_INTERVAL   = 1
CHECKPOINT_SECS = 60
WAIT_TIMEOUT    = 5
TETHER_KEYWORDS = ["rndis", "remote ndis", "android", "usb ethernet", "usb tether", "ethernet 4", "ethernet 5"]
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


def get_logged_bytes_for_date(date_str):
    """Sum only Session: values for a specific date."""
    total = 0.0
    if not os.path.exists(LOG_FILE):
        return total
    pat = re.compile(
        r"^\[" + re.escape(date_str) + r"\].*\|  Session:\s*([\d\.]+\s*(?:TB|GB|MB|KB|B))\s*\|"
    )
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if not line.startswith("[" + date_str + "]"):
                continue
            m = pat.search(line)
            if m:
                total += human_to_bytes(m.group(1))
    return total


def write_log_line(date_str, start_time, end_time, recv, sent, reason=""):
    """Write one log line for a given date."""
    ts       = int((end_time - start_time).total_seconds())
    h, rem   = divmod(ts, 3600)
    m, s     = divmod(rem, 60)
    dur      = "{}h {}m {}s".format(h, m, s) if h else "{}m {}s".format(m, s)
    tag      = "  [{}]".format(reason) if reason else ""
    sess_b   = recv + sent

    if sess_b == 0 and reason != "reloaded":
        return None

    daily = get_logged_bytes_for_date(date_str)
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


def log_session(iface, start_time, end_time, recv_bytes, sent_bytes, reason=""):
    """
    Log a session, splitting at midnight if it crosses a day boundary.
    Data is split proportionally by time.
    """
    # Check if session crosses midnight
    start_date = start_time.date()
    end_date   = end_time.date()

    if start_date == end_date:
        # Same day — single entry
        write_log_line(
            start_time.strftime("%Y-%m-%d"),
            start_time, end_time,
            recv_bytes, sent_bytes, reason
        )
        return

    # Crosses midnight — split proportionally
    # Midnight = start of end_date
    midnight = datetime.combine(end_date, datetime.min.time())

    total_secs  = (end_time - start_time).total_seconds()
    before_secs = (midnight - start_time).total_seconds()
    after_secs  = (end_time - midnight).total_seconds()

    if total_secs == 0:
        return

    ratio_before = before_secs / total_secs
    ratio_after  = after_secs  / total_secs

    recv_before = int(recv_bytes * ratio_before)
    sent_before = int(sent_bytes * ratio_before)
    recv_after  = recv_bytes - recv_before
    sent_after  = sent_bytes - sent_before

    # Log pre-midnight portion under old date
    write_log_line(
        start_time.strftime("%Y-%m-%d"),
        start_time,
        midnight - timedelta(seconds=1),
        recv_before, sent_before,
        reason="midnight split"
    )

    # Log post-midnight portion under new date
    write_log_line(
        end_time.strftime("%Y-%m-%d"),
        midnight,
        end_time,
        recv_after, sent_after,
        reason if reason else ""
    )


def write_live_status(iface, start_time, recv, sent, status="connected"):
    elapsed    = (datetime.now() - start_time).total_seconds()
    today      = datetime.now().strftime("%Y-%m-%d")
    daily_prev = get_logged_bytes_for_date(today)
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

            # Graceful shutdown for hot-reload
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

            # Update live status using today's date for daily_prev
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