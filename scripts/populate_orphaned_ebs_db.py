#!/usr/bin/env python3
"""
Run ad hoc: scans AWS for unattached EBS volumes and fills the Postgres table.
Set DATABASE_URL before running. Table is created if missing, then replaced with fresh data.
"""

import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from app.scanner_ebs import scan_all_regions_ebs
from app.db import get_database_url, get_connection, create_table_ebs, truncate_and_insert_ebs


def main() -> int:
    try:
        get_database_url()
    except ValueError as e:
        print(f"Error: {e}")
        return 1

    print("Scanning AWS regions for unattached EBS volumes...")
    results = scan_all_regions_ebs()

    rows = []
    for r in results:
        if r.error:
            print(f"  Skip {r.region}: {r.error}")
            continue
        for vol in r.orphaned:
            rows.append(vol.to_dict())

    print(f"Found {len(rows)} unattached EBS volumes.")

    with get_connection() as conn:
        create_table_ebs(conn)
        truncate_and_insert_ebs(conn, rows)

    print("Database table updated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
