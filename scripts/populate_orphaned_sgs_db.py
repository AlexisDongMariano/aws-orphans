#!/usr/bin/env python3
"""
Run ad hoc: scans AWS for orphaned security groups and fills the Postgres table.
Set DATABASE_URL before running. Table is created if missing, then replaced with fresh data.
"""

import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from app.scanner import scan_all_regions
from app.db import get_database_url, get_connection, create_table, truncate_and_insert


def main() -> int:
    # Fail fast if DB is not configured (before running the long AWS scan)
    try:
        get_database_url()
    except ValueError as e:
        print(f"Error: {e}")
        return 1

    print("Scanning AWS regions for orphaned security groups...")
    results = scan_all_regions()

    rows = []
    for r in results:
        if r.error:
            print(f"  Skip {r.region}: {r.error}")
            continue
        for sg in r.orphaned:
            rows.append(sg.to_dict())

    print(f"Found {len(rows)} orphaned security groups.")

    with get_connection() as conn:
        create_table(conn)
        truncate_and_insert(conn, rows)

    print("Database table updated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
