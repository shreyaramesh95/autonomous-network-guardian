"""The probe seam.

The monitoring engine never touches the network directly - it asks a
``ProbeProvider`` for results. Two implementations exist:

* ``LiveProbes``      - real ICMP ping / socket / DNS (best effort)
* ``SimulatedProbes`` - deterministic results from the simulation scenario

Everything above this seam (storage, diagnosis, incidents, health, UI) is
identical in both modes. This is what makes demos deterministic (PRD 33) and
the diagnosis engine unit-testable without a network.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class ProbeResult:
    """Outcome of probing one device (PRD 7)."""

    reachable: bool
    latency_ms: Optional[float] = None      # round-trip average, None when unreachable
    packet_loss_pct: float = 0.0            # 0-100


@dataclass
class ServiceResult:
    """Outcome of a DNS or internet/WAN check (PRD 9 / 10)."""

    reachable: bool
    latency_ms: Optional[float] = None
    detail: str = ""


class ProbeProvider(ABC):
    @abstractmethod
    def probe_device(self, ip: str) -> ProbeResult:
        """Ping a device: reachability, latency, packet loss."""

    @abstractmethod
    def check_dns(self, hostname: str) -> ServiceResult:
        """Resolve a hostname to distinguish DNS failure from WAN failure."""

    @abstractmethod
    def check_internet(self, ip: str, port: int) -> ServiceResult:
        """Reach an external IP directly (no name resolution involved)."""
