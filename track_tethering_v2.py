"""
USB Tethering Data Tracker v2.1
================================
Tracks data usage per tethering session with timestamps.
Appends each session to 'data_log.txt' in the same folder.

Changelog v2.1:
  - Each log line now shows cumulative daily total
  - Fixed UnicodeEncodeError on Windows terminal (ASCII spinner)
"""

import psutil
import time
import os
import re
from datetime import datetime

# --- CONFIG ------------------------------------------------------------------
LOG_FILE        = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data_log.txt")
POLL_INTERVAL   = 3
CHECKPOINT_SECS = 60
WAIT_TIMEOUT    = 5
TETHER_KEYWORDS = ["rndis", "remote ndis", "android", "usb ethernet", "usb tether", "ethernet 4"]
SPINNER         = ["|", "/", "-", "\\"]
# -----------------------------------------------------------------------------


def bytes_to_human(n):
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if n < 1024:
            return "{:.2f} {}".format(n, unit)
        n /= 1024
    return "{:.2f} PB".format(n)


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


def get_daily_bytes_so_far(date_str):
    """
    Sum all session totals already logged for date_str.
    Handles all 3 log formats:
      v1.0 -> Total: X  (no Session: label)
      v2.0 -> Total: X  (with Down:/Up: labels)
      v2.1 -> Session: X  Day Total: Y
    """
    if not os.path.exists(LOG_FILE):
        return 0.0

    total = 0.0
    prefix = r"^\[" + re.escape(date_str) + r"\]"

    # v2.1 format: Session: X
    pat_session = re.compile(prefix + r".*Session:\s*([\d\.]+\s*(?:TB|GB|MB|KB|B))")
    # v1/v2.0 format: Total: X  (only count if no Session: present)
    pat_total   = re.compile(prefix + r".*Total:\s*([\d\.]+\s*(?:TB|GB|MB|KB|B))")

    with open(LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if not line.startswith("[" + date_str + "]"):
                continue
            m = pat_session.search(line)
            if m:
                total += human_to_bytes(m.group(1))
                continue
            # fallback: old format used Total: for session amount
            m = pat_total.search(line)
            if m:
                total += human_to_bytes(m.group(1))
    return total


def find_tether_interface():
    try:
        for name, stat in psutil.net_if_stats().items():
            if any(kw in name.lower() for kw in TETHER_KEYWORDS) and stat.isup:
                return name
    except Exception:
        pass
    return None


def is_interface_alive(iface_name):
    try:
        stats = psutil.net_if_stats()
        return iface_name in stats and stats[iface_name].isup
    except Exception:
        return False


def get_interface_bytes(iface_name):
    try:
        counters = psutil.net_io_counters(pernic=True)
        if iface_name in counters:
            c = counters[iface_name]
            return c.bytes_recv, c.bytes_sent
    except Exception:
        pass
    return 0, 0


def log_session(iface, start_time, end_time, recv, sent, reason=""):
    total_secs   = int((end_time - start_time).total_seconds())
    h, rem       = divmod(total_secs, 3600)
    m, s         = divmod(rem, 60)
    dur          = "{}h {}m {}s".format(h, m, s) if h else "{}m {}s".format(m, s)
    tag          = "  [{}]".format(reason) if reason else ""
    date_str     = start_time.strftime("%Y-%m-%d")
    sess_total   = recv + sent
    cumulative   = get_daily_bytes_so_far(date_str) + sess_total

    line = "[{}]  {} -> {}  |  Duration: {}  |  Down: {}  Up: {}  |  Session: {}  |  Day Total: {}{}\n".format(
        date_str,
        start_time.strftime("%I:%M:%S %p"),
        end_time.strftime("%I:%M:%S %p"),
        dur,
        bytes_to_human(recv),
        bytes_to_human(sent),
        bytes_to_human(sess_total),
        bytes_to_human(cumulative),
        tag
    )

    is_new = not os.path.exists(LOG_FILE)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        if is_new:
            f.write("USB Tethering Data Usage Log\n")
            f.write("=" * 130 + "\n")
        f.write(line)
    return line


def checkpoint_session(iface, start_time, recv, sent):
    cp  = os.path.join(os.path.dirname(LOG_FILE), ".checkpoint.tmp")
    now = datetime.now()
    ts  = int((now - start_time).total_seconds())
    h, rem = divmod(ts, 3600)
    m, s   = divmod(rem, 60)
    with open(cp, "w", encoding="utf-8") as f:
        f.write("[CHECKPOINT {}]  Started: {}  |  Running: {}h {}m {}s  |  Session: {}\n".format(
            now.strftime("%Y-%m-%d %H:%M:%S"),
            start_time.strftime("%I:%M:%S %p"),
            h, m, s,
            bytes_to_human(recv + sent)
        ))


def clear_checkpoint():
    cp = os.path.join(os.path.dirname(LOG_FILE), ".checkpoint.tmp")
    if os.path.exists(cp):
        os.remove(cp)


def wait_for_reconnect(session_count):
    print("\n" + "-" * 60)
    print("  Session #{} saved. Phone unplugged.".format(session_count))
    print("  Waiting for reconnect... (Ctrl+C to exit)\n")
    i = 0
    while True:
        iface = find_tether_interface()
        if iface:
            return iface
        print("\r  {}  Waiting for USB tethering...   ".format(SPINNER[i % 4]), end="", flush=True)
        i += 1
        time.sleep(WAIT_TIMEOUT)


def run_session(iface, num):
    print("\n" + "-" * 60)
    print("  Session #{}  |  Interface: {}".format(num, iface))
    print("  Log: {}".format(LOG_FILE))
    print("  Unplug = auto-save  |  Ctrl+C = save and exit\n")

    start                        = datetime.now()
    baseline_recv, baseline_sent = get_interface_bytes(iface)
    prev_recv,     prev_sent     = baseline_recv, baseline_sent
    s_recv,        s_sent        = 0, 0
    last_cp                      = time.time()

    try:
        while True:
            time.sleep(POLL_INTERVAL)

            # Phone unplugged
            if not is_interface_alive(iface):
                end    = datetime.now()
                logged = log_session(iface, start, end, s_recv, s_sent, reason="unplugged")
                clear_checkpoint()
                print("\n\n  [UNPLUG] Session #{} saved:".format(num))
                print("  " + logged.strip())
                return "unplugged"

            c_recv, c_sent = get_interface_bytes(iface)

            # Counter reset guard
            if c_recv < prev_recv or c_sent < prev_sent:
                baseline_recv = c_recv - s_recv
                baseline_sent = c_sent - s_sent

            s_recv = c_recv - baseline_recv
            s_sent = c_sent - baseline_sent

            # 60s checkpoint
            if time.time() - last_cp >= CHECKPOINT_SECS:
                checkpoint_session(iface, start, s_recv, s_sent)
                last_cp = time.time()

            # Live display
            el     = int((datetime.now() - start).total_seconds())
            h, rem = divmod(el, 3600)
            m, s   = divmod(rem, 60)
            tstr   = "{}h {:02d}m {:02d}s".format(h, m, s) if h else "{:02d}m {:02d}s".format(m, s)

            print(
                "\r  {}  |  Down: {}  Up: {}  |  Session: {}   ".format(
                    tstr,
                    bytes_to_human(s_recv),
                    bytes_to_human(s_sent),
                    bytes_to_human(s_recv + s_sent)
                ),
                end="", flush=True
            )
            prev_recv, prev_sent = c_recv, c_sent

    except KeyboardInterrupt:
        end    = datetime.now()
        logged = log_session(iface, start, end, s_recv, s_sent, reason="manual exit")
        clear_checkpoint()
        print("\n\n  [STOPPED] Session #{} saved:".format(num))
        print("  " + logged.strip())
        print("\n  Full log -> {}".format(LOG_FILE))
        return "manual_exit"


def main():
    print("=" * 60)
    print("  USB Tethering Data Tracker  v2.1")
    print("=" * 60)
    print("  Each log line shows cumulative daily total")
    print("  Unplug/replug freely  |  Ctrl+C to exit")
    print("=" * 60)

    iface = find_tether_interface()

    if not iface:
        print("\n  Phone not detected. Plug in USB tethering...\n")
        i = 0
        try:
            while not iface:
                print("\r  {}  Waiting...   ".format(SPINNER[i % 4]), end="", flush=True)
                time.sleep(WAIT_TIMEOUT)
                iface = find_tether_interface()
                i += 1
        except KeyboardInterrupt:
            print("\n\n  Exiting. No sessions recorded.")
            return

    n = 0
    while True:
        n += 1
        result = run_session(iface, n)

        if result == "manual_exit":
            print("\n  Sessions this run: {}  |  Goodbye!".format(n))
            break

        try:
            iface = wait_for_reconnect(n)
            print("\r  Reconnected! Starting session #{}...   ".format(n + 1))
            time.sleep(1)
        except KeyboardInterrupt:
            print("\n\n  Exiting. Sessions this run: {}  |  Goodbye!".format(n))
            break


if __name__ == "__main__":
    main()