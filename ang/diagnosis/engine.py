"""Diagnosis engine (PRD 11, 30 steps 6-11).

Runs every candidate rule against an Observation, compares their scores, and
produces one explained diagnosis: root cause, confidence, priority, affected
devices, evidence, recommended action and the full hypothesis ranking.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

from .observation import Observation
from .recommendations import actions_for
from .rules import ALL_RULES
from .scoring import Evidence, confidence_for


@dataclass
class Diagnosis:
    root_cause: str
    rule_name: str
    confidence: int
    priority: str
    reasoning: str
    affected: list[dict] = field(default_factory=list)      # {name, reason}
    evidence: list[dict] = field(default_factory=list)      # {text, detail, score}
    actions: list[str] = field(default_factory=list)
    hypotheses: list[dict] = field(default_factory=list)    # {key,label,score} ranked
    is_fault: bool = False
    timestamp: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class DiagnosisEngine:
    def __init__(self, config):
        self.config = config
        self.threshold = (config.get("INCIDENT_SCORE_THRESHOLD")
                          if hasattr(config, "get") else config["INCIDENT_SCORE_THRESHOLD"])

    def diagnose(self, obs: Observation) -> Diagnosis:
        hyps = [rule(obs, self.config) for rule in ALL_RULES]
        hyps.sort(key=lambda h: h.score, reverse=True)
        ranked = [{"key": h.key, "label": h.label, "score": h.score} for h in hyps]

        top = hyps[0]
        if top.score < self.threshold:
            return self._healthy(obs, ranked)

        # Scope escalation (PRD 15): a Medium fault that hits many devices -> High.
        priority = top.priority
        if priority == "Medium" and len(top.affected) >= 3:
            priority = "High"

        return Diagnosis(
            root_cause=top.label,
            rule_name=top.key,
            confidence=confidence_for(top.key, top.score),
            priority=priority,
            reasoning=top.reasoning,
            affected=[{"name": n, "reason": r} for n, r in top.affected],
            evidence=[_ev(e) for e in top.evidence],
            actions=top.actions or actions_for(top.key),
            hypotheses=ranked,
            is_fault=True,
            timestamp=obs.timestamp,
        )

    def _healthy(self, obs: Observation, ranked: list[dict]) -> Diagnosis:
        online = sum(1 for d in obs.devices if d.reachable)
        total = len(obs.devices)
        ev = [
            Evidence(f"All {total} devices reachable", f"{online}/{total} online", 0),
            Evidence("Gateway reachable",
                     obs.gateway.name if obs.gateway else "n/a", 0),
            Evidence("DNS resolution succeeded" if obs.dns_ok else "DNS resolution failing",
                     obs.dns_detail, 0),
            Evidence("External endpoint reachable" if obs.internet_ok else "External endpoint failing",
                     obs.internet_detail, 0),
        ]
        return Diagnosis(
            root_cause="Healthy network — no fault",
            rule_name="no_fault",
            confidence=confidence_for("no_fault", 99),
            priority="None",
            reasoning="Every fault hypothesis scored below the incident "
                      "threshold, so no incident was created.",
            affected=[],
            evidence=[_ev(e) for e in ev],
            actions=actions_for("no_fault"),
            hypotheses=ranked,
            is_fault=False,
            timestamp=obs.timestamp,
        )


def _ev(e: Evidence) -> dict:
    sign = "+" if e.score >= 0 else ""
    return {"text": e.text, "detail": e.detail, "score": f"{sign}{e.score}"}
