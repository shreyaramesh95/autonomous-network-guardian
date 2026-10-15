"""Recommended troubleshooting actions per diagnosis (PRD 16)."""
from __future__ import annotations

ACTIONS: dict[str, list[str]] = {
    "gateway_failure": [
        "Check router power.",
        "Check Ethernet cables.",
        "Verify gateway configuration.",
        "Check router interface status.",
    ],
    "dns_failure": [
        "Check DNS server configuration.",
        "Check DNS service availability.",
        "Try an alternate DNS resolver.",
    ],
    "internet_failure": [
        "Check WAN connection.",
        "Check router external interface.",
        "Check ISP connectivity or status page.",
    ],
    "individual_device_failure": [
        "Check device power.",
        "Check network cable or Wi-Fi association.",
        "Check local network configuration.",
        "Check network adapter status.",
    ],
    "high_latency": [
        "Check network congestion.",
        "Inspect cables and interfaces.",
        "Check gateway performance.",
        "Investigate overloaded devices or links.",
    ],
    "packet_loss": [
        "Check network congestion.",
        "Inspect cables and interfaces.",
        "Check gateway performance.",
        "Investigate overloaded devices or links.",
    ],
    "no_fault": [
        "No action required.",
        "Continue monitoring on the configured cycle.",
    ],
}


def actions_for(key: str) -> list[str]:
    return list(ACTIONS.get(key, ["Investigate manually."]))
