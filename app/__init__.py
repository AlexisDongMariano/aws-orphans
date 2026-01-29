"""AWS Orphans scanner - reusable for CLI and FastAPI."""

from app.regions import REGIONS, get_regions
from app.scanner import (
    find_orphaned_security_groups,
    scan_region_for_orphaned_sgs,
    scan_all_regions,
    security_group_console_url,
    OrphanedSGResult,
)

__all__ = [
    "REGIONS",
    "get_regions",
    "find_orphaned_security_groups",
    "scan_region_for_orphaned_sgs",
    "scan_all_regions",
    "security_group_console_url",
    "OrphanedSGResult",
]
