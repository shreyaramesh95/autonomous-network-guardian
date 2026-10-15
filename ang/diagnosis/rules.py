"""Candidate fault rules (PRD 11.1, 12, 34).

Every rule is a pure function ``(Observation, config) -> Hypothesis``. A rule
that does not apply returns a hypothesis with score 0. The engine compares all
of them and picks the strongest - it never declares a root cause from a single
failed test (PRD 34).
"""
from __future__ import annotations

from .observation import Observation
from .recommendations import actions_for
from .scoring import Builder, Hypothesis

# PRD 15 priority per rule (scope can escalate it in the engine).
PRIORITY = {
    "gateway_failure": "Critical",
    "internet_failure": "Critical",
    "dns_failure": "High",
    "high_latency": "High",
    "packet_loss": "High",
    "individual_device_failure": "Medium",
    "no_fault": "None",
}

LABEL = {
    "gateway_failure": "Gateway failure",
    "internet_failure": "Internet / WAN failure",
    "dns_failure": "DNS failure",
    "high_latency": "Shared network degradation — high latency",
    "packet_loss": "Shared network degradation — packet loss",
    "individual_device_failure": "Individual device failure",
    "no_fault": "Healthy network — no fault",
}


def _hyp(key: str, score: int, b: Builder, **kw) -> Hypothesis:
    return Hypothesis(
        key=key, label=kw.get("label", LABEL[key]), score=score, evidence=b.items,
        priority=kw.get("priority", PRIORITY[key]),
        affected=kw.get("affected", []), actions=actions_for(key),
        reasoning=kw.get("reasoning", ""),
    )


# --- shared-dependency: gateway failure (PRD 12) ----------------------------
def rule_gateway_failure(obs: Observation, config) -> Hypothesis:
    b = Builder()
    gw = obs.gateway
    if gw is None:
        return _hyp("gateway_failure", 0, b)

    down = obs.unreachable_non_gateway
    dependents_down = [d for d in down if d.depends_on == gw.id]

    if gw.reachable or len(dependents_down) < 2:
        return _hyp("gateway_failure", 0, b,
                    reasoning="Gateway responding or fewer than two dependent "
                              "devices affected — shared-dependency hypothesis "
                              "not supported.")

    names = ", ".join(d.name for d in dependents_down)
    b.add("Multiple devices affected", names, 30)
    b.add("Gateway unreachable", f"{gw.name} {gw.ip}", 40)
    if not obs.internet_ok:
        b.add("Internet unavailable", obs.internet_detail or "external endpoint unreachable", 20)
    if not obs.dns_ok:
        b.add("DNS unavailable", obs.dns_detail or "name resolution failing", 10)

    affected = [(d.name, f"shared dependency {gw.name}") for d in dependents_down]
    reasoning = (
        f"{names} all depend on {gw.name}. Their simultaneous failure together "
        f"with an unreachable gateway is better explained by one shared fault "
        f"than by {len(dependents_down)} independent device faults."
    )
    return _hyp("gateway_failure", b.score, b, affected=affected, reasoning=reasoning)


# --- individual device failure (PRD 34) ------------------------------------
def rule_individual_device_failure(obs: Observation, config) -> Hypothesis:
    b = Builder()
    down = obs.unreachable_non_gateway

    if len(down) != 1 or not obs.gateway_reachable:
        return _hyp("individual_device_failure", 0, b,
                    reasoning="More than one device down, or the gateway is also "
                              "down — points away from a single-device fault.")

    d0 = down[0]
    b.add("Exactly one device unreachable", f"{d0.name} ({d0.ip})", 50)
    if obs.gateway_reachable and obs.gateway is not None:
        b.add("Gateway reachable", f"{obs.gateway.name}, {_ms(obs.gateway.latency_ms)}", 20)
    peers = [d for d in obs.devices if d.id != d0.id and not d.is_gateway]
    if peers and all(p.reachable for p in peers):
        b.add("Peer devices healthy", f"{len(peers)}/{len(peers)} reachable", 10)
    if obs.dns_ok and obs.internet_ok:
        b.add("External connectivity normal", "DNS + internet OK", 8)

    return _hyp("individual_device_failure", b.score, b,
                label=f"Individual device failure — {d0.name}",
                affected=[(d0.name, "unreachable, ICMP timeout")],
                reasoning=f"Only {d0.name} is unreachable while the gateway and "
                          f"every peer respond, so the shared-dependency "
                          f"hypothesis is not supported.")


# --- DNS failure vs internet failure (PRD 9 / 10 / 34) --------------------
def rule_dns_failure(obs: Observation, config) -> Hypothesis:
    b = Builder()
    if not obs.gateway_reachable or not obs.internet_ok or obs.dns_ok:
        return _hyp("dns_failure", 0, b,
                    reasoning="DNS is resolving, or the fault is broader than "
                              "name resolution.")
    if obs.unreachable_non_gateway:
        return _hyp("dns_failure", 0, b,
                    reasoning="Devices are unreachable — the fault is not "
                              "confined to name resolution.")

    b.add("DNS resolution failed", obs.dns_detail or "SERVFAIL", 44)
    if obs.gateway is not None:
        b.add("Gateway reachable", f"{obs.gateway.name}, {_ms(obs.gateway.latency_ms)}", 20)
    b.add("External IP reachable", obs.internet_detail or "external endpoint reachable", 20)

    affected = [(d.name, "cannot resolve hostnames") for d in obs.clients]
    return _hyp("dns_failure", b.score, b, affected=affected,
                label="DNS failure",
                reasoning="The gateway responds and an external IP address is "
                          "reachable, so the fault is isolated to name "
                          "resolution rather than general connectivity.")


def rule_internet_failure(obs: Observation, config) -> Hypothesis:
    b = Builder()
    if not obs.gateway_reachable or obs.internet_ok:
        return _hyp("internet_failure", 0, b,
                    reasoning="External endpoint reachable, or the gateway "
                              "itself is down (a gateway fault, not WAN).")
    if obs.unreachable_non_gateway:
        return _hyp("internet_failure", 0, b,
                    reasoning="Local devices are unreachable — not a pure WAN "
                              "fault.")

    b.add("External endpoint unreachable", obs.internet_detail or "5/5 lost", 46)
    if obs.gateway is not None:
        b.add("Gateway reachable", f"{obs.gateway.name}, {_ms(obs.gateway.latency_ms)}", 20)
    b.add("All local devices reachable", f"{len(obs.devices)}/{len(obs.devices)} online", 12)
    if not obs.dns_ok:
        b.add("DNS resolution failed", "consistent with WAN loss", 8)

    affected = [(d.name, "no external access") for d in obs.clients]
    return _hyp("internet_failure", b.score, b, affected=affected,
                reasoning="Local devices and the gateway are healthy while the "
                          "external test endpoint is unreachable, which points "
                          "past the gateway to the WAN link.")


# --- shared degradation: latency / packet loss (PRD 11.1) ----------------
def rule_high_latency(obs: Observation, config) -> Hypothesis:
    b = Builder()
    moderate = _cfg(config, "LATENCY_MODERATE_MS")
    good = _cfg(config, "LATENCY_GOOD_MS")
    if obs.unreachable_non_gateway:
        return _hyp("high_latency", 0, b)

    elevated = [d for d in obs.devices
                if d.reachable and d.latency_ms is not None and d.latency_ms > moderate]
    if len(elevated) < 3:
        return _hyp("high_latency", 0, b,
                    reasoning="Fewer than three targets above the latency "
                              "threshold — not a shared degradation.")

    rng = f"{int(min(d.latency_ms for d in elevated))}-{int(max(d.latency_ms for d in elevated))} ms"
    b.add(f"Latency above threshold on {len(elevated)} targets", rng, 40)
    b.add("No unreachable devices", f"{len(obs.devices)}/{len(obs.devices)} online", 16)
    gw = obs.gateway
    if gw is not None and gw.latency_ms is not None and gw.latency_ms > good:
        b.add("Gateway latency also elevated", f"{gw.name} {int(gw.latency_ms)} ms", 16)

    affected = [(d.name, f"{int(d.latency_ms)} ms") for d in elevated]
    return _hyp("high_latency", b.score, b, affected=affected,
                reasoning="Every target is reachable but round-trip times rose "
                          "together, which suggests congestion on the shared "
                          "segment rather than a device fault.")


def rule_packet_loss(obs: Observation, config) -> Hypothesis:
    b = Builder()
    threshold = _cfg(config, "PACKET_LOSS_THRESHOLD_PCT")
    if obs.unreachable_non_gateway:
        return _hyp("packet_loss", 0, b)

    lossy = [d for d in obs.devices
             if d.reachable and d.packet_loss_pct > threshold]
    if len(lossy) < 3:
        return _hyp("packet_loss", 0, b,
                    reasoning="Fewer than three targets above the loss "
                              "threshold — not a shared degradation.")

    rng = f"{int(min(d.packet_loss_pct for d in lossy))}-{int(max(d.packet_loss_pct for d in lossy))}%"
    b.add("Packet loss above threshold", f"{rng} on {len(lossy)} targets", 44)
    b.add("All devices still reachable", f"{len(obs.devices)}/{len(obs.devices)} online", 16)
    gw = obs.gateway
    if gw is not None and gw.packet_loss_pct > threshold:
        b.add("Loss present on gateway path", f"{gw.name} {int(gw.packet_loss_pct)}%", 16)

    affected = [(d.name, f"{int(d.packet_loss_pct)}% loss") for d in lossy]
    return _hyp("packet_loss", b.score, b, affected=affected,
                reasoning="Sustained loss on several targets that share the same "
                          "gateway path, with no target fully unreachable.")


ALL_RULES = [
    rule_gateway_failure,
    rule_individual_device_failure,
    rule_dns_failure,
    rule_internet_failure,
    rule_high_latency,
    rule_packet_loss,
]


# --- helpers ---------------------------------------------------------------
def _ms(v) -> str:
    return "—" if v is None else f"{v:g} ms"


def _cfg(config, key):
    return config.get(key) if hasattr(config, "get") else config[key]
