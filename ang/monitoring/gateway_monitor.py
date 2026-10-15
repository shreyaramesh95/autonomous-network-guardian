"""Gateway reachability check (PRD 8).

The gateway is an ordinary device row with role 'Gateway'; this wrapper just
names the check for readability and returns the same ProbeResult.
"""
from __future__ import annotations

from .probes import ProbeProvider, ProbeResult


def check_gateway(provider: ProbeProvider, gateway_ip: str, config) -> ProbeResult:
    return provider.probe_device(gateway_ip)
