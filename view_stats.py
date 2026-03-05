"""
view_stats.py
=============
Read-only live dashboard for USB Tethering Data Tracker.
Reads live_status.tmp and data_log.txt written by background tracker.

Run anytime:  python view_stats.py
Close with Ctrl+C — background tracker is NOT affected.
"""

import time
import os
import re
from datetime import datetime

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
LOG_FILE  = os.path.join(BASE_DIR, "data_log.txt")
LIVE_FILE = os.path.join(BASE_DIR, "live_status.tmp")
REFRESH   = 1

BOLD   = "\033[1m"
DIM    = "\033[2m"
GREEN  = "\033[92m"
CYAN   = "\033[96m"
YELLOW = "\033[93m"
RED    = "\033[91m"
RESET  = "\033[0m"
LINE   = "-" * 76


def bytes_to_human(n):
    try:
        n = float(n)
    except Exception:
        return "?"
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


def read_live_status():
    data = {"status": "unknown"}
    if not os.path.exists(LIVE_FILE):
        return data
    try:
        with open(LIVE_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if "=" in line:
                    k, v = line.split("=", 1)
                    data[k.strip()] = v.strip()
    except Exception:
        pass
    return data


def get_todays_sessions():
    """Return list of sessions logged today + total bytes."""
    today    = datetime.now().strftime("%Y-%m-%d")
    sessions = []
    daily_b  = 0.0

    if not os.path.exists(LOG_FILE):
        return sessions, daily_b

    pat = re.compile(
        r"^\[" + re.escape(today) + r"\]\s+(.+?)\s+->\s+(.+?)\s+\|"
        r".*?Duration:\s*([^\|]+)\|"
        r".*?Down:\s*([\d\.]+\s*(?:TB|GB|MB|KB|B))"
        r"\s+Up:\s*([\d\.]+\s*(?:TB|GB|MB|KB|B))"
        r".*?\|  Session:\s*([\d\.]+\s*(?:TB|GB|MB|KB|B))\s*\|"
    )
    pat_reason = re.compile(r"\[(unplugged|manual exit|reloaded|midnight split)\]")

    with open(LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if not line.startswith("[" + today + "]"):
                continue
            m = pat.search(line)
            if not m:
                continue
            total_b  = human_to_bytes(m.group(6))
            daily_b += total_b
            reason_m = pat_reason.search(line)
            sessions.append({
                "start":    m.group(1).strip(),
                "end":      m.group(2).strip(),
                "duration": m.group(3).strip(),
                "recv":     m.group(4).strip(),
                "sent":     m.group(5).strip(),
                "total":    bytes_to_human(total_b),
                "reason":   reason_m.group(1) if reason_m else "",
            })

    return sessions, daily_b


def format_elapsed(seconds):
    seconds = int(float(seconds))
    h, rem  = divmod(seconds, 3600)
    m, s    = divmod(rem, 60)
    return "{}h {:02d}m {:02d}s".format(h, m, s) if h else "{:02d}m {:02d}s".format(m, s)


def draw(sessions, daily_so_far, live):
    os.system("cls")

    status    = live.get("status", "unknown")
    iface     = live.get("iface", "—")
    updated   = live.get("updated", "—")
    live_recv = float(live.get("recv", 0))
    live_sent = float(live.get("sent", 0))
    live_el   = float(live.get("elapsed", 0))
    live_tot  = live_recv + live_sent
    grand     = daily_so_far + live_tot

    out = []
    out.append(BOLD + CYAN + "  USB Tethering — Live Stats" + RESET +
               DIM + "  (read-only, Ctrl+C to close)" + RESET)
    out.append("  " + DIM + "Now: {}  |  Tracker update: {}".format(
        datetime.now().strftime("%I:%M:%S %p"), updated) + RESET)
    out.append("  " + LINE)

    if sessions:
        out.append(BOLD + "  Today's Sessions:" + RESET)
        for i, sess in enumerate(sessions, 1):
            tag = DIM + " [{}]".format(sess["reason"]) + RESET if sess["reason"] else ""
            out.append(
                "  #{:<2}  {}  ->  {}  |  {}  |  "
                "Down: {}  Up: {}  |  {}{}".format(
                    i,
                    sess["start"], sess["end"],
                    sess["duration"],
                    sess["recv"], sess["sent"],
                    YELLOW + sess["total"] + RESET,
                    tag
                )
            )
    else:
        out.append(DIM + "  No sessions logged today yet." + RESET)

    out.append("  " + LINE)

    if status == "connected":
        out.append(BOLD + GREEN + "  >> LIVE  |  Interface: {}".format(iface) + RESET)
        out.append("     Time:     {}".format(format_elapsed(live_el)))
        out.append("     Down:     {}    Up: {}".format(
            bytes_to_human(live_recv), bytes_to_human(live_sent)))
        out.append("     Session:  " + CYAN + bytes_to_human(live_tot) + RESET)
    elif status == "waiting":
        out.append(RED + "  Phone unplugged — waiting for reconnect..." + RESET)
    elif status == "idle":
        out.append(DIM + "  Tracker idle — no active session." + RESET)
    else:
        out.append(RED + "  Tracker not running or live_status.tmp not found." + RESET)
        out.append(DIM + "  Make sure track_tethering_v2.py is running." + RESET)

    out.append("  " + LINE)
    out.append(BOLD + "  Day Total: " + YELLOW + bytes_to_human(grand) + RESET)
    out.append("  " + LINE)
    out.append("")
    print("\n".join(out), end="", flush=True)


def main():
    os.system("color")
    try:
        while True:
            sessions, daily_so_far = get_todays_sessions()
            live = read_live_status()
            draw(sessions, daily_so_far, live)
            time.sleep(REFRESH)
    except KeyboardInterrupt:
        os.system("cls")
        print("\n  Viewer closed. Background tracker still running.\n")


if __name__ == "__main__":
    main()