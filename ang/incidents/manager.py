"""Incident manager (PRD 17-20).

Called once per monitoring cycle with the fresh diagnosis + health score. It:

* opens an incident when a fault is confirmed (anti-flap: FAILURE_CONFIRM_CYCLES)
* keeps an open incident's confidence / priority / affected devices current
* confirms recovery over RECOVERY_CONFIRM_CYCLES clean cycles, then auto-closes
  the incident and records its duration (PRD 19)
* writes the diagnostic-event timeline (PRD 20)
"""
from __future__ import annotations

from datetime import datetime, timezone

from ..database import models as m
from ..diagnosis.engine import Diagnosis
from ..diagnosis.observation import Observation
from .health import HealthScore


def format_duration(seconds: float) -> str:
    seconds = max(0, int(round(seconds)))
    minutes, secs = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m {secs}s"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts)


def incident_code(incident_id: int) -> str:
    return f"INC-{incident_id:03d}"


class IncidentManager:
    def __init__(self, config):
        self.config = config
        self.failure_confirm = int(_cfg(config, "FAILURE_CONFIRM_CYCLES"))
        self.recovery_confirm = int(_cfg(config, "RECOVERY_CONFIRM_CYCLES"))
        # rule_name -> consecutive fault cycles seen before an incident exists
        self._pending: dict[str, int] = {}

    # -- called every cycle -------------------------------------------------
    def sync(self, conn, diagnosis: Diagnosis, obs: Observation,
             health: HealthScore, now: str | None = None) -> dict:
        now = now or datetime.now(timezone.utc).isoformat(timespec="seconds")
        actions: list[str] = []

        if diagnosis.is_fault:
            self._pending = {k: v for k, v in self._pending.items()
                             if k == diagnosis.rule_name}
            existing = m.open_incident_for_rule(conn, diagnosis.rule_name)
            if existing is not None:
                m.touch_incident(conn, existing["id"], diagnosis.confidence,
                                 diagnosis.priority, now)
                self._write_affected(conn, existing["id"], diagnosis, obs)
                actions.append(f"updated {incident_code(existing['id'])}")
            else:
                seen = self._pending.get(diagnosis.rule_name, 0) + 1
                self._pending[diagnosis.rule_name] = seen
                if seen >= self.failure_confirm:
                    inc_id = self._open(conn, diagnosis, obs, health, now)
                    self._pending.pop(diagnosis.rule_name, None)
                    actions.append(f"opened {incident_code(inc_id)}")
                else:
                    actions.append(
                        f"fault pending ({seen}/{self.failure_confirm})")
            # a different fault taking over supersedes unrelated open incidents
            self._supersede_others(conn, diagnosis.rule_name, now, actions)
        else:
            self._pending.clear()
            for inc in m.open_incidents(conn):
                cycles = m.bump_recovery(conn, inc["id"])
                if cycles >= self.recovery_confirm:
                    self._close(conn, inc, now, health,
                                reason="recovery confirmed")
                    actions.append(f"resolved {incident_code(inc['id'])}")
                else:
                    actions.append(
                        f"{incident_code(inc['id'])} recovering "
                        f"({cycles}/{self.recovery_confirm})")

        conn.commit()
        return {"time": now, "actions": actions}

    # -- helpers ----------------------------------------------------------
    def _open(self, conn, diagnosis: Diagnosis, obs: Observation,
              health: HealthScore, now: str) -> int:
        inc_id = m.create_incident(
            conn, diagnosis.root_cause, diagnosis.rule_name,
            diagnosis.confidence, diagnosis.priority, now, health.score)

        self._write_affected(conn, inc_id, diagnosis, obs)

        m.add_diagnostic_event(conn, inc_id, "incident_opened",
                               f"{diagnosis.root_cause} — priority "
                               f"{diagnosis.priority.upper()}", now)
        for ev in diagnosis.evidence:
            m.add_diagnostic_event(conn, inc_id, diagnosis.rule_name,
                                   f"{ev['text']} · {ev['detail']} ({ev['score']})", now)
        m.add_diagnostic_event(conn, inc_id, "confidence_score",
                               f"Weighted evidence total {diagnosis.confidence} of 100", now)
        if diagnosis.actions:
            m.add_diagnostic_event(conn, inc_id, "recommendation",
                                   "; ".join(diagnosis.actions), now)
        m.add_diagnostic_event(conn, inc_id, "health_score",
                               f"Health score {health.score} / 100 ({health.status})", now)
        return inc_id

    def _write_affected(self, conn, inc_id: int, diagnosis: Diagnosis,
                        obs: Observation) -> None:
        by_name = {d.name: d.id for d in obs.devices}
        rows = [(by_name[a["name"]], a["reason"])
                for a in diagnosis.affected if a["name"] in by_name]
        if rows:
            m.set_incident_devices(conn, inc_id, rows)

    def _close(self, conn, inc, now: str, health: HealthScore, reason: str) -> None:
        try:
            duration = format_duration(
                (_parse(now) - _parse(inc["started_at"])).total_seconds())
        except ValueError:
            duration = ""
        m.resolve_incident(conn, inc["id"], now, duration)
        m.add_diagnostic_event(conn, inc["id"], "recovery_confirmed",
                               f"{reason} over {self.recovery_confirm} cycles — "
                               f"duration {duration}", now)
        m.add_diagnostic_event(conn, inc["id"], "health_score",
                               f"Health score restored to {health.score} / 100", now)

    def _supersede_others(self, conn, active_rule: str, now: str,
                          actions: list[str]) -> None:
        for inc in m.open_incidents(conn):
            if inc["rule_name"] != active_rule:
                cycles = m.bump_recovery(conn, inc["id"])
                if cycles >= self.recovery_confirm:
                    try:
                        duration = format_duration(
                            (_parse(now) - _parse(inc["started_at"])).total_seconds())
                    except ValueError:
                        duration = ""
                    m.resolve_incident(conn, inc["id"], now, duration)
                    m.add_diagnostic_event(
                        conn, inc["id"], "superseded",
                        f"symptoms replaced by {active_rule} — duration {duration}", now)
                    actions.append(f"superseded {incident_code(inc['id'])}")


def _cfg(config, key):
    return config.get(key) if hasattr(config, "get") else config[key]
