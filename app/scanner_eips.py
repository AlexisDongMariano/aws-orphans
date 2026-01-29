"""Scanner for unassociated (orphaned) Elastic IPs. Same regions as security groups."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from app.regions import REGIONS, get_regions

logger = logging.getLogger(__name__)


def elastic_ip_console_url(region: str, allocation_id: str) -> str:
    """AWS EC2 console URL for an Elastic IP (for hyperlinks in web app)."""
    return (
        f"https://{region}.console.aws.amazon.com/ec2/home"
        f"?region={region}#ElasticIpDetails:AllocationId={allocation_id}"
    )


@dataclass
class OrphanedEIPResult:
    """Result for a single unassociated Elastic IP."""

    region: str
    allocation_id: str
    public_ip: str
    domain: str  # vpc or standard

    @property
    def console_url(self) -> str:
        return elastic_ip_console_url(self.region, self.allocation_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "region": self.region,
            "allocation_id": self.allocation_id,
            "public_ip": self.public_ip,
            "domain": self.domain,
            "console_url": self.console_url,
        }


@dataclass
class RegionEIPScanResult:
    region: str
    orphaned: list[OrphanedEIPResult] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "region": self.region,
            "orphaned": [o.to_dict() for o in self.orphaned],
            "count": len(self.orphaned),
            "error": self.error,
        }


def find_orphaned_elastic_ips(ec2_client: Any, region: str) -> list[OrphanedEIPResult]:
    """Find Elastic IPs in the region that are not associated with any instance/ENI."""
    try:
        addrs = ec2_client.describe_addresses()["Addresses"]
        orphaned: list[OrphanedEIPResult] = []
        for a in addrs:
            if a.get("AssociationId"):
                continue
            orphaned.append(
                OrphanedEIPResult(
                    region=region,
                    allocation_id=a.get("AllocationId", ""),
                    public_ip=a.get("PublicIp", ""),
                    domain=a.get("Domain", "vpc"),
                )
            )
        return orphaned
    except ClientError as e:
        logger.exception("EC2 API error in %s: %s", region, e)
        raise
    except NoCredentialsError:
        logger.exception("No AWS credentials")
        raise


def scan_region_for_orphaned_eips(
    region: str,
    session: boto3.Session | None = None,
) -> RegionEIPScanResult:
    """Scan a single region for unassociated Elastic IPs."""
    session = session or boto3.Session()
    try:
        ec2 = session.client("ec2", region_name=region)
        orphaned = find_orphaned_elastic_ips(ec2, region)
        return RegionEIPScanResult(region=region, orphaned=orphaned)
    except Exception as e:
        return RegionEIPScanResult(region=region, error=str(e))


def scan_all_regions_eips(
    regions: list[str] | None = None,
    session: boto3.Session | None = None,
) -> list[RegionEIPScanResult]:
    """Scan multiple regions for unassociated Elastic IPs."""
    regions = regions or REGIONS
    regions = get_regions(regions)
    session = session or boto3.Session()
    return [scan_region_for_orphaned_eips(r, session) for r in regions]
