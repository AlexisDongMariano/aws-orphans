"""Scanner for orphaned (unassociated) security groups. Reusable by CLI and FastAPI."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from app.regions import REGIONS, get_regions

logger = logging.getLogger(__name__)


def security_group_console_url(region: str, group_id: str) -> str:
    """AWS EC2 console URL for a security group (for hyperlinks in web app)."""
    return (
        f"https://{region}.console.aws.amazon.com/ec2/home"
        f"?region={region}#SecurityGroup:groupId={group_id}"
    )


@dataclass
class OrphanedSGResult:
    """Result for a single orphaned security group."""

    region: str
    group_id: str
    group_name: str
    description: str
    vpc_id: str | None

    @property
    def console_url(self) -> str:
        """AWS console URL for this security group (use as hyperlink)."""
        return security_group_console_url(self.region, self.group_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "region": self.region,
            "group_id": self.group_id,
            "group_name": self.group_name,
            "description": self.description,
            "vpc_id": self.vpc_id,
            "console_url": self.console_url,
        }


@dataclass
class RegionScanResult:
    """Result of scanning one region for orphaned SGs."""

    region: str
    orphaned: list[OrphanedSGResult] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "region": self.region,
            "orphaned": [o.to_dict() for o in self.orphaned],
            "count": len(self.orphaned),
            "error": self.error,
        }


def find_orphaned_security_groups(
    ec2_client: Any,
    region: str,
    *,
    exclude_default_sg: bool = True,
) -> list[OrphanedSGResult]:
    """
    Find security groups in the given region that are not attached to any ENI.

    Uses describe_security_groups and describe_network_interfaces. SGs attached to
    ENIs (EC2, RDS, Lambda in VPC, ELB, etc.) are considered in use.

    Args:
        ec2_client: boto3 EC2 client for the region.
        region: Region name (for result attribution).
        exclude_default_sg: If True, skip the default security group (cannot be deleted).

    Returns:
        List of OrphanedSGResult for SGs not associated with any network interface.
    """
    try:
        paginator = ec2_client.get_paginator("describe_security_groups")
        security_groups = []
        for page in paginator.paginate():
            security_groups.extend(page.get("SecurityGroups", []))

        eni_paginator = ec2_client.get_paginator("describe_network_interfaces")
        used_sg_ids: set[str] = set()
        for page in eni_paginator.paginate():
            for eni in page.get("NetworkInterfaces", []):
                for group in eni.get("Groups", []):
                    used_sg_ids.add(group.get("GroupId", ""))

        orphaned: list[OrphanedSGResult] = []
        for sg in security_groups:
            group_id = sg.get("GroupId", "")
            group_name = sg.get("GroupName", "")
            if group_id in used_sg_ids:
                continue
            if exclude_default_sg and group_name == "default":
                continue
            orphaned.append(
                OrphanedSGResult(
                    region=region,
                    group_id=group_id,
                    group_name=group_name,
                    description=sg.get("Description", ""),
                    vpc_id=sg.get("VpcId"),
                )
            )
        return orphaned
    except ClientError as e:
        logger.exception("EC2 API error in %s: %s", region, e)
        raise
    except NoCredentialsError:
        logger.exception("No AWS credentials")
        raise


def scan_region_for_orphaned_sgs(
    region: str,
    *,
    exclude_default_sg: bool = True,
    session: boto3.Session | None = None,
) -> RegionScanResult:
    """
    Scan a single region for orphaned security groups.

    Returns a RegionScanResult with either orphaned list or error message.
    """
    session = session or boto3.Session()
    try:
        ec2 = session.client("ec2", region_name=region)
        orphaned = find_orphaned_security_groups(
            ec2, region, exclude_default_sg=exclude_default_sg
        )
        return RegionScanResult(region=region, orphaned=orphaned)
    except Exception as e:  # noqa: BLE001
        return RegionScanResult(region=region, error=str(e))


def scan_all_regions(
    regions: list[str] | None = None,
    *,
    exclude_default_sg: bool = True,
    session: boto3.Session | None = None,
) -> list[RegionScanResult]:
    """
    Scan multiple regions for orphaned security groups.

    Args:
        regions: List of region codes. If None, uses REGIONS from app.regions.
        exclude_default_sg: If True, skip default SG in each region.
        session: Optional boto3 session (for custom profile/credentials).

    Returns:
        List of RegionScanResult, one per region. Failed regions have error set.
    """
    regions = regions or REGIONS
    regions = get_regions(regions)
    session = session or boto3.Session()
    results: list[RegionScanResult] = []
    for region in regions:
        results.append(
            scan_region_for_orphaned_sgs(
                region,
                exclude_default_sg=exclude_default_sg,
                session=session,
            )
        )
    return results
