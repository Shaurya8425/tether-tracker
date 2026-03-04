"""
fix_log.py
==========
Recalculates all Day Total values in data_log.txt correctly.
Only reads Session: values (not Day Total:) to avoid double-counting.
Creates a backup before changing anything.

Run once:  python fix_log.py
"""

import re
import os
import shutil
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "data_log.txt")
BACKUP   = os.path.join(BASE_DIR, "data_log_backup_fix.txt")


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


def fix_log():
    if not os.path.exists(LOG_FILE):
        print("ERROR: data_log.txt not found at " + LOG_FILE)
        return

    # Backup first
    shutil.copy2(LOG_FILE, BACKUP)
    print("Backup saved to: " + BACKUP)

    with open(LOG_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Pattern to extract Session: value only (not Day Total:)
    # Uses word boundary — matches "Session:" but NOT "Day Total:"
    pat_session = re.compile(
        r"^(\[\d{4}-\d{2}-\d{2}\].*?\|  Session:\s*)([\d\.]+\s*(?:TB|GB|MB|KB|B))"
        r"(  \|  Day Total:\s*)([\d\.]+\s*(?:TB|GB|MB|KB|B))(.*)"
    )
    pat_date = re.compile(r"^\[(\d{4}-\d{2}-\d{2})\]")

    new_lines  = []
    daily_totals = {}  # date -> running bytes

    fixed_count = 0

    for line in lines:
        # Header/separator — keep as-is
        if line.startswith("USB Tethering") or line.startswith("=") or line.strip() == "":
            new_lines.append(line)
            continue

        m = pat_session.match(line)
        if not m:
            new_lines.append(line)
            continue

        date_m = pat_date.match(line)
        if not date_m:
            new_lines.append(line)
            continue

        date_str    = date_m.group(1)
        sess_bytes  = human_to_bytes(m.group(2))
        old_daytot  = m.group(4).strip()

        # Accumulate correctly using only session bytes
        daily_totals[date_str] = daily_totals.get(date_str, 0.0) + sess_bytes
        correct_total = bytes_to_human(daily_totals[date_str])

        if correct_total != old_daytot:
            fixed_count += 1

        # Rebuild line with correct Day Total
        new_line = m.group(1) + m.group(2) + m.group(3) + correct_total + m.group(5)
        if not new_line.endswith("\n"):
            new_line += "\n"
        new_lines.append(new_line)

    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

    print("\nDone! Fixed {} line(s).".format(fixed_count))
    print("\nCorrected daily summaries:")
    for date, total in sorted(daily_totals.items()):
        print("  {}  ->  {}".format(date, bytes_to_human(total)))
    print("\nOriginal backed up at: " + BACKUP)


if __name__ == "__main__":
    fix_log()