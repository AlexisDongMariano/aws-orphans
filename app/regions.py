"""AWS regions to scan (from console screenshot)."""

# Regions from the screenshot: United States, Asia Pacific, Canada, Europe, Middle East, South America
REGIONS = [
    # United States
    "us-east-1",   # N. Virginia
    "us-east-2",   # Ohio
    "us-west-1",   # N. California
    "us-west-2",   # Oregon
    # Asia Pacific
    "ap-southeast-5",  # Malaysia
    "ap-south-1",      # Mumbai
    "ap-northeast-3",  # Osaka
    "ap-northeast-2",  # Seoul
    "ap-southeast-1",  # Singapore
    "ap-southeast-2",  # Sydney
    "ap-northeast-1",  # Tokyo
    # Canada
    "ca-central-1",  # Central
    "ca-west-1",     # Calgary
    # Europe
    "eu-central-1",  # Frankfurt
    "eu-west-1",     # Ireland
    "eu-west-2",     # London
    "eu-west-3",     # Paris
    "eu-north-1",    # Stockholm
    # Middle East
    "me-south-1",   # Bahrain
    "me-central-1",  # UAE
    # South America
    "sa-east-1",    # São Paulo
]


def get_regions(subset: list[str] | None = None) -> list[str]:
    """Return regions to scan. If subset is given, filter to those (invalid codes are skipped)."""
    if subset is None:
        return list(REGIONS)
    valid = set(REGIONS)
    return [r for r in subset if r in valid]
