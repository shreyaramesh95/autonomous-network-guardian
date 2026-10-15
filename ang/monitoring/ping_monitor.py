"""Device reachability, latency and packet-loss checks (PRD 7)."""
from __future__ import annotations

from .probes import ProbeProvider, ProbeResult

GOOD, MODERATE, HIGH, CRITICAL = "good", "moderate", "high", "critical"


def classify_latency(latency_ms, config) -> str | None:
    """PRD 7.2 table: 0-50 good / 50-100 moderate / 100-200 high / >200 critical."""
    if latency_ms is None:
        return None
    if latency_ms <= config["LATENCY_GOOD_MS"]:
        return GOOD
    if latency_ms <= config["LATENCY_MODERATE_MS"]:
        return MODERATE
    if latency_ms <= config["LATENCY_HIGH_MS"]:
        return HIGH
    return CRITICAL


def status_from_probe(result: ProbeResult, config) -> str:
    if not result.reachable:
        return "offline"
    if result.packet_loss_pct > config["PACKET_LOSS_THRESHOLD_PCT"]:
        return "degraded"
    if classify_latency(result.latency_ms, config) in (HIGH, CRITICAL):
        return "degraded"
    return "online"


def check_device(provider: ProbeProvider, ip: str, config) -> ProbeResult:
    return provider.probe_device(ip)
