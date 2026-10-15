"""Evidence and confidence primitives (PRD 13 / 14).

Each rule builds a list of ``Evidence`` items with a score contribution; the
hypothesis score is their sum. Confidence is the score, capped per rule so the
number reads as a diagnostic score rather than a probability (PRD 14).
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Evidence:
    text: str          # short, dashboard-facing
    detail: str        # the measurement it came from
    score: int         # contribution to the hypothesis score


@dataclass
class Hypothesis:
    key: str
    label: str
    score: int
    evidence: list[Evidence] = field(default_factory=list)
    priority: str = "Low"
    affected: list[tuple[str, str]] = field(default_factory=list)  # (device_name, reason)
    actions: list[str] = field(default_factory=list)
    reasoning: str = ""

    @property
    def evidence_total(self) -> int:
        return sum(e.score for e in self.evidence)


# Per-rule confidence cap. Gateway is capped a touch lower because its raw
# evidence can reach exactly 100 (PRD 14 example) and we never claim certainty.
CONFIDENCE_CAP = {
    "gateway_failure": 95,
    "internet_failure": 96,
    "dns_failure": 95,
    "individual_device_failure": 95,
    "high_latency": 90,
    "packet_loss": 90,
    "no_fault": 99,
}
DEFAULT_CAP = 95


def confidence_for(key: str, score: int) -> int:
    return max(0, min(CONFIDENCE_CAP.get(key, DEFAULT_CAP), score))


class Builder:
    """Small helper to accumulate evidence + score inside a rule."""

    def __init__(self) -> None:
        self.items: list[Evidence] = []

    def add(self, text: str, detail: str, score: int) -> None:
        self.items.append(Evidence(text, detail, score))

    @property
    def score(self) -> int:
        return sum(e.score for e in self.items)
