"""Scanner for unattached (available) EBS volumes. Same regions as security groups."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from app.regions import REGIONS, get_regions

logger = logging.getLogger(__name__)


def ebs_volume_console_url(region: str, volume_id: str) -> str:
    """AWS EC2 console URL for an EBS volume (for hyperlinks in web app)."""
    return (
        f"https://{region}.console.aws.amazon.com/ec2/v2/home"
        f"?region={region}#VolumeDetails:VolumeId={volume_id}"
    )


@dataclass
class UnattachedEBSResult:
    """Result for a single unattached EBS volume (state=available)."""

    region: str
    volume_id: str
    size_gb: int
    volume_type: str
    availability_zone: str
    create_time: str  # ISO format for display/DB

    @property
    def console_url(self) -> str:
        return ebs_volume_console_url(self.region, self.volume_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "region": self.region,
            "volume_id": self.volume_id,
            "size_gb": self.size_gb,
            "volume_type": self.volume_type,
            "availability_zone": self.availability_zone,
            "create_time": self.create_time,
            "console_url": self.console_url,
        }


@dataclass
class RegionEBSScanResult:
    region: str
    orphaned: list[UnattachedEBSResult] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "region": self.region,
            "orphaned": [o.to_dict() for o in self.orphaned],
            "count": len(self.orphaned),
            "error": self.error,
        }


def find_unattached_ebs_volumes(ec2_client: Any, region: str) -> list[UnattachedEBSResult]:
    """Find EBS volumes in the region with state 'available' (unattached)."""
    try:
        paginator = ec2_client.get_paginator("describe_volumes")
        volumes: list[dict] = []
        for page in paginator.paginate(Filters=[{"Name": "status", "Values": ["available"]}]):
            volumes.extend(page.get("Volumes", []))

        result: list[UnattachedEBSResult] = []
        for v in volumes:
            create_time = v.get("CreateTime")
            if isinstance(create_time, datetime):
                create_time = create_time.isoformat()
            else:
                create_time = str(create_time or "")
            result.append(
                UnattachedEBSResult(
                    region=region,
                    volume_id=v.get("VolumeId", ""),
                    size_gb=int(v.get("Size", 0)),
                    volume_type=v.get("VolumeType", ""),
                    availability_zone=v.get("AvailabilityZone", ""),
                    create_time=create_time,
                )
            )
        return result
    except ClientError as e:
        logger.exception("EC2 API error in %s: %s", region, e)
        raise
    except NoCredentialsError:
        logger.exception("No AWS credentials")
        raise


def scan_region_for_unattached_ebs(
    region: str,
    session: boto3.Session | None = None,
) -> RegionEBSScanResult:
    """Scan a single region for unattached EBS volumes."""
    session = session or boto3.Session()
    try:
        ec2 = session.client("ec2", region_name=region)
        orphaned = find_unattached_ebs_volumes(ec2, region)
        return RegionEBSScanResult(region=region, orphaned=orphaned)
    except Exception as e:
        return RegionEBSScanResult(region=region, error=str(e))


def scan_all_regions_ebs(
    regions: list[str] | None = None,
    session: boto3.Session | None = None,
) -> list[RegionEBSScanResult]:
    """Scan multiple regions for unattached EBS volumes."""
    regions = regions or REGIONS
    regions = get_regions(regions)
    session = session or boto3.Session()
    return [scan_region_for_unattached_ebs(r, session) for r in regions]
