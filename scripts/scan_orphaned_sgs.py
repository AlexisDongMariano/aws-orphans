#!/usr/bin/env python3
"""
CLI script to scan AWS regions for orphaned (unassociated) security groups.

Uses the same app.scanner module that FastAPI can import for web endpoints.
"""

import argparse
import json
import sys
from pathlib import Path

# Allow running from project root: python scripts/scan_orphaned_sgs.py
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from app.scanner import scan_all_regions, scan_region_for_orphaned_sgs
from app.regions import REGIONS, get_regions


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scan AWS regions for orphaned (unassociated) security groups."
    )
    parser.add_argument(
        "--regions",
        nargs="*",
        default=None,
        metavar="REGION",
        help=f"Regions to scan (default: all {len(REGIONS)} regions from config).",
    )
    parser.add_argument(
        "--include-default-sg",
        action="store_true",
        help="Include default security group in orphan list (normally excluded).",
    )
    parser.add_argument(
        "--profile",
        default=None,
        help="AWS profile name (optional).",
    )
    parser.add_argument(
        "--output",
        choices=("table", "json"),
        default="table",
        help="Output format: table (human) or json.",
    )
    args = parser.parse_args()

    session = None
    if args.profile:
        import boto3
        session = boto3.Session(profile_name=args.profile)

    results = scan_all_regions(
        regions=args.regions,
        exclude_default_sg=not args.include_default_sg,
        session=session,
    )

    if args.output == "json":
        out = [r.to_dict() for r in results]
        print(json.dumps(out, indent=2))
        return 0

    # Table output
    total_orphaned = 0
    for r in results:
        if r.error:
            print(f"[{r.region}] ERROR: {r.error}")
            continue
        count = len(r.orphaned)
        total_orphaned += count
        if count == 0:
            print(f"[{r.region}] No orphaned security groups.")
        else:
            print(f"[{r.region}] {count} orphaned security group(s):")
            for sg in r.orphaned:
                vpc = sg.vpc_id or "EC2-Classic"
                print(f"  - {sg.group_id}  {sg.group_name}  (VPC: {vpc})")
                print(f"    {sg.console_url}")

    print()
    print(f"Total orphaned SGs across regions: {total_orphaned}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
