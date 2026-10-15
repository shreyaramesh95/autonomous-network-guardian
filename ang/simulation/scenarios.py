"""Deterministic fault scenarios (PRD 22).

Each scenario fully describes what every probe should return, so a demo is
perfectly repeatable. Numbers are aligned with the UI mockup's ``SCEN`` table.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Base healthy round-trip latency per seed device (ms), from the mockup.
BASE_LATENCY_MS = {
    "192.168.1.1": 2,     # RTR-01
    "192.168.1.10": 8,    # PC-01
    "192.168.1.11": 11,   # PC-02
    "192.168.1.12": 9,    # PC-03
    "192.168.1.20": 4,    # SRV-01
    "192.168.1.30": 14,   # PRN-01
}
DEFAULT_BASE_LATENCY_MS = 12  # any device not in the seed set

# Packet-loss percentage per device while the "packet_loss" scenario is active.
LOSS_PATTERN_PCT = {
    "192.168.1.1": 18,
    "192.168.1.10": 30,
    "192.168.1.11": 40,
    "192.168.1.12": 20,
    "192.168.1.20": 6,
    "192.168.1.30": 25,
}
DEFAULT_LOSS_PCT = 22


@dataclass(frozen=True)
class Scenario:
    key: str
    label: str
    note: str
    down_ips: frozenset = field(default_factory=frozenset)
    dns_ok: bool = True
    internet_ok: bool = True
    degrade: str | None = None          # None | "latency" | "loss"
    reference_health: int = 98          # mockup parity, not authoritative


_G = "192.168.1.1"
_P1, _P2, _P3 = "192.168.1.10", "192.168.1.11", "192.168.1.12"

SCENARIOS: dict[str, Scenario] = {
    "healthy": Scenario(
        "healthy", "Healthy network",
        "All monitored targets responding. No fault hypothesis exceeds threshold.",
        reference_health=98),
    "device": Scenario(
        "device", "Individual device failure",
        "PC-02 unreachable while the gateway and its peers stay healthy.",
        down_ips=frozenset({_P2}), reference_health=82),
    "gateway": Scenario(
        "gateway", "Gateway failure",
        "Three clients, the gateway and external connectivity failed in the same cycle.",
        down_ips=frozenset({_P1, _P2, _P3, _G}), dns_ok=False, internet_ok=False,
        reference_health=34),
    "dns": Scenario(
        "dns", "DNS failure",
        "Gateway and external IP reachable; name resolution failing.",
        dns_ok=False, internet_ok=True, reference_health=61),
    "internet": Scenario(
        "internet", "Internet / WAN failure",
        "Local network intact, gateway reachable, external endpoint unreachable.",
        dns_ok=False, internet_ok=False, reference_health=55),
    "high_latency": Scenario(
        "high_latency", "High latency",
        "All targets reachable with round-trip times above the moderate threshold.",
        degrade="latency", reference_health=74),
    "packet_loss": Scenario(
        "packet_loss", "Packet loss",
        "Reachability intact, sustained loss across the shared segment.",
        degrade="loss", reference_health=68),
    "recovery": Scenario(
        "recovery", "Recovery",
        "All targets restored; any open incident closes automatically once "
        "recovery is confirmed.",
        reference_health=96),
}

# API endpoint suffix (PRD 26) -> scenario key
ENDPOINT_TO_KEY = {
    "device-failure": "device",
    "gateway-failure": "gateway",
    "dns-failure": "dns",
    "internet-failure": "internet",
    "high-latency": "high_latency",
    "packet-loss": "packet_loss",
    "recovery": "recovery",
    "reset": "healthy",
}
