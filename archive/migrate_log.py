"""
migrate_log.py
==============
One-time script to rewrite old data_log.txt entries
into the v2.1 format with Session: and Day Total: fields.

Run once:  python migrate_log.py
It creates a backup at data_log_backup.txt before changing anything.
"""

import re
import os
import shutil
from datetime import datetime

LOG_FILE   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data_log.txt")
BACKUP     = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data_log_backup.txt")


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


def parse_line(line):
    """
    Parse any version of a log line.
    Returns dict with keys: date, start, end, duration, recv, sent,
                            session_bytes, reason, raw
    or None if line is a header/separator.
    """
    # Skip headers
    if line.startswith("USB Tethering") or line.startswith("=") or line.strip() == "":
        return None

    # Must start with [YYYY-MM-DD]
    date_match = re.match(r"^\[(\d{4}-\d{2}-\d{2})\]", line)
    if not date_match:
        return None

    date_str = date_match.group(1)

    # Already v2.1 format — has Session: and Day Total:
    if "Session:" in line and "Day Total:" in line:
        return {"already_migrated": True, "date": date_str, "raw": line}

    # Extract reason tag [unplugged] / [manual exit]
    reason = ""
    reason_match = re.search(r"\[(unplugged|manual exit)\]", line)
    if reason_match:
        reason = reason_match.group(1)

    # Extract duration
    dur_match = re.search(r"Duration:\s*([^\|]+)", line)
    duration = dur_match.group(1).strip() if dur_match else "?"

    # Extract start -> end times (handles both → and ->)
    time_match = re.search(
        r"\d{4}-\d{2}-\d{2}\]\s+(\d{2}:\d{2}:\d{2}\s*[AP]M)\s*[→-]+>?\s*(\d{2}:\d{2}:\d{2}\s*[AP]M)",
        line
    )
    start_str = time_match.group(1).strip() if time_match else "?"
    end_str   = time_match.group(2).strip() if time_match else "?"

    # Extract recv/sent
    # v1 format: ↓ X ↑ Y
    v1_match = re.search(
        r"↓\s*([\d\.]+\s*(?:TB|GB|MB|KB|B))\s*↑\s*([\d\.]+\s*(?:TB|GB|MB|KB|B))",
        line
    )
    # v2 format: Down: X  Up: Y
    v2_match = re.search(
        r"Down:\s*([\d\.]+\s*(?:TB|GB|MB|KB|B))\s+Up:\s*([\d\.]+\s*(?:TB|GB|MB|KB|B))",
        line
    )

    if v1_match:
        recv_str = v1_match.group(1)
        sent_str = v1_match.group(2)
    elif v2_match:
        recv_str = v2_match.group(1)
        sent_str = v2_match.group(2)
    else:
        return None  # can't parse

    recv_bytes = human_to_bytes(recv_str)
    sent_bytes = human_to_bytes(sent_str)
    sess_bytes = recv_bytes + sent_bytes

    return {
        "already_migrated": False,
        "date":      date_str,
        "start":     start_str,
        "end":       end_str,
        "duration":  duration,
        "recv":      recv_bytes,
        "sent":      sent_bytes,
        "session":   sess_bytes,
        "reason":    reason,
        "raw":       line
    }


def build_new_line(entry, cumulative):
    tag = "  [{}]".format(entry["reason"]) if entry["reason"] else ""
    return "[{}]  {} -> {}  |  Duration: {}  |  Down: {}  Up: {}  |  Session: {}  |  Day Total: {}{}\n".format(
        entry["date"],
        entry["start"],
        entry["end"],
        entry["duration"],
        bytes_to_human(entry["recv"]),
        bytes_to_human(entry["sent"]),
        bytes_to_human(entry["session"]),
        bytes_to_human(cumulative),
        tag
    )


def migrate():
    if not os.path.exists(LOG_FILE):
        print("ERROR: data_log.txt not found at", LOG_FILE)
        return

    # Backup first
    shutil.copy2(LOG_FILE, BACKUP)
    print("Backup created: {}".format(BACKUP))

    with open(LOG_FILE, "r", encoding="utf-8") as f:
        raw_lines = f.readlines()

    # Parse all lines
    entries    = [parse_line(l) for l in raw_lines]
    new_lines  = []
    daily_totals = {}  # date_str -> running bytes

    for i, entry in enumerate(entries):
        raw = raw_lines[i]

        # Header / separator lines — keep as-is
        if entry is None:
            new_lines.append(raw)
            continue

        # Already v2.1 — extract session bytes for daily running total
        if entry["already_migrated"]:
            m = re.search(r"Session:\s*([\d\.]+\s*(?:TB|GB|MB|KB|B))", raw)
            if m:
                b = human_to_bytes(m.group(1))
                daily_totals[entry["date"]] = daily_totals.get(entry["date"], 0) + b
            new_lines.append(raw)
            continue

        # Old format — rewrite with Day Total
        date = entry["date"]
        daily_totals[date] = daily_totals.get(date, 0) + entry["session"]
        new_lines.append(build_new_line(entry, daily_totals[date]))

    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

    print("\nMigration complete!")
    print("Lines processed: {}".format(len(raw_lines)))
    print("\nDaily summaries:")
    for date, total in sorted(daily_totals.items()):
        print("  {}  ->  {}".format(date, bytes_to_human(total)))
    print("\nYour original file is backed up at:", BACKUP)


if __name__ == "__main__":
    migrate()