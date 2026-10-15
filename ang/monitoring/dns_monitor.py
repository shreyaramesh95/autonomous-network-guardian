"""DNS resolution check (PRD 9).

Kept separate from the internet check so the diagnosis engine can tell a DNS
failure apart from a general WAN outage.
"""
from __future__ import annotations

from .probes import ProbeProvider, ServiceResult


def check_dns(provider: ProbeProvider, config) -> ServiceResult:
    return provider.check_dns(config["DNS_TEST_HOSTNAME"])
