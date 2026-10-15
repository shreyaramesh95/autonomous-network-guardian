"""Internet / WAN connectivity check (PRD 10).

Reaches an external IP directly (no DNS involved) so a WAN outage is
distinguishable from a DNS failure.
"""
from __future__ import annotations

from .probes import ProbeProvider, ServiceResult


def check_internet(provider: ProbeProvider, config) -> ServiceResult:
    return provider.check_internet(config["INTERNET_TEST_IP"], config["INTERNET_TEST_PORT"])
