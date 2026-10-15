"""Network health score, 0-100 (PRD 21).

Weighted sum of six factors (weights in ``config.HEALTH_WEIGHTS``, sum = 100).
Every factor also reports the points it lost and why, so the dashboard can show
the reasons for a significant drop (PRD 21).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..diagnosis.observation import Observation


@dataclass
class HealthFactor:
    name: str
    points: float
    max_points: float
    note: str = ""

    @property
    def lost(self) -> float:
        return self.max_points - self.points


@dataclass
class HealthScore:
    score: int
    status: str                       # HEALTHY | DEGRADED | CRITICAL
    factors: list[HealthFactor] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "status": self.status,
            "factors": [
                {"name": f.name, "points": round(f.points, 1),
                 "max": f.max_points, "note": f.note}
                for f in self.factors
            ],
            "reasons": self.reasons,
        }


def _status(score: int) -> str:
    if score >= 90:
        return "HEALTHY"
    if score >= 60:
        return "DEGRADED"
    return "CRITICAL"


def _latency_health(latency_ms, good, moderate, high) -> float:
    if latency_ms is None or latency_ms <= moderate:
        return 1.0
    if latency_ms <= high:
        return 0.4
    return 0.0


def _loss_health(loss_pct, threshold) -> float:
    if loss_pct <= threshold:
        return 1.0
    # linear from threshold -> 0 down to 60% -> 0
    span = max(1.0, 60.0 - threshold)
    return max(0.0, 1.0 - (loss_pct - threshold) / span)


def compute_health(obs: Observation, config) -> HealthScore:
    get = config.get if hasattr(config, "get") else config.__getitem__
    W = get("HEALTH_WEIGHTS")
    good = get("LATENCY_GOOD_MS")
    moderate = get("LATENCY_MODERATE_MS")
    high = get("LATENCY_HIGH_MS")
    loss_threshold = get("PACKET_LOSS_THRESHOLD_PCT")

    devices = obs.devices or []
    total = len(devices) or 1
    reachable = [d for d in devices if d.reachable]

    # 1. device availability
    avail = W["device_availability"] * (len(reachable) / total)
    avail_note = f"{len(reachable)}/{total} devices reachable"

    # 2. latency (over reachable devices)
    if reachable:
        lat_ratio = sum(_latency_health(d.latency_ms, good, moderate, high)
                        for d in reachable) / len(reachable)
    else:
        lat_ratio = 0.0
    latency = W["latency"] * lat_ratio
    slow = [d.name for d in reachable
            if d.latency_ms is not None and d.latency_ms > moderate]
    lat_note = "within thresholds" if not slow else f"elevated on {', '.join(slow)}"

    # 3. packet loss (over reachable devices)
    if reachable:
        loss_ratio = sum(_loss_health(d.packet_loss_pct, loss_threshold)
                         for d in reachable) / len(reachable)
    else:
        loss_ratio = 0.0
    loss = W["packet_loss"] * loss_ratio
    lossy = [d.name for d in reachable if d.packet_loss_pct > loss_threshold]
    loss_note = "no significant loss" if not lossy else f"loss on {', '.join(lossy)}"

    # 4. gateway
    gw = obs.gateway
    if gw is None:
        gateway, gw_note = W["gateway"], "no gateway registered"
    elif not gw.reachable:
        gateway, gw_note = 0.0, f"{gw.name} unreachable"
    elif gw.packet_loss_pct > loss_threshold or (
            gw.latency_ms is not None and gw.latency_ms > high):
        gateway, gw_note = W["gateway"] * 0.5, f"{gw.name} degraded"
    else:
        gateway, gw_note = W["gateway"], f"{gw.name} reachable"

    # 5. DNS
    dns = W["dns"] if obs.dns_ok else 0.0
    dns_note = "resolving" if obs.dns_ok else "resolution failing"

    # 6. internet / WAN
    internet = W["internet"] if obs.internet_ok else 0.0
    inet_note = "reachable" if obs.internet_ok else "external endpoint unreachable"

    factors = [
        HealthFactor("Device availability", avail, W["device_availability"], avail_note),
        HealthFactor("Latency", latency, W["latency"], lat_note),
        HealthFactor("Packet loss", loss, W["packet_loss"], loss_note),
        HealthFactor("Gateway health", gateway, W["gateway"], gw_note),
        HealthFactor("DNS health", dns, W["dns"], dns_note),
        HealthFactor("Internet connectivity", internet, W["internet"], inet_note),
    ]
    raw = sum(f.points for f in factors)
    score = max(0, min(100, round(raw)))

    reasons = [f"{f.name}: {f.note} (-{round(f.lost)})"
               for f in factors if f.lost >= 4]

    return HealthScore(score=score, status=_status(score), factors=factors,
                       reasons=reasons)
