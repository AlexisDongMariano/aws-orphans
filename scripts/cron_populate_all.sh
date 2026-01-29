#!/bin/bash
# Run all populate scripts (SGs, EIPs, EBS). Use from cron.
# Requires: DATABASE_URL (and AWS creds for scanning) in .env next to this script's project root.

set -e
cd "$(dirname "$0")/.."

if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

.venv/bin/python3 scripts/populate_orphaned_sgs_db.py
.venv/bin/python3 scripts/populate_orphaned_eips_db.py
.venv/bin/python3 scripts/populate_orphaned_ebs_db.py
