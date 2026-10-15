"""Phase 4 - incident lifecycle, recovery auto-close, network health score."""
from __future__ import annotations

import pytest

from ang.database.db import connection
from ang.database import models as m
from ang.incidents.health import compute_health
from ang.incidents.manager import format_duration
from ang.diagnosis.observation import Observation
from ang.simulation.simulator import SimulatedProbes, Simulator

from .conftest import config_dict


@pytest.fixture()
def engine(app):
    eng = app.extensions["ang_engine"]
    reg = app.extensions["ang_registry"]
    return eng, reg


def _open(db_path):
    with connection(db_path) as c:
        return m.open_incidents(c)


def _all(db_path):
    with connection(db_path) as c:
        return m.list_incidents(c)


# --- health score (PRD 21) --------------------------------------------------
def test_health_score_healthy_is_high(db_path):
    cfg = config_dict(DATABASE=db_path)
    sim = Simulator(cfg); sim.set_scenario("healthy")
    with connection(db_path) as c:
        obs = Observation.from_provider(m.list_devices(c), SimulatedProbes(sim), cfg)
    h = compute_health(obs, cfg)
    assert h.score >= 95
    assert h.status == "HEALTHY"
    assert h.reasons == []


def test_health_score_gateway_failure_is_critical(db_path):
    cfg = config_dict(DATABASE=db_path)
    sim = Simulator(cfg); sim.set_scenario("gateway")
    with connection(db_path) as c:
        obs = Observation.from_provider(m.list_devices(c), SimulatedProbes(sim), cfg)
    h = compute_health(obs, cfg)
    assert h.score < 40                       # PRD 21.2
    assert h.status == "CRITICAL"
    assert any("Gateway" in r for r in h.reasons)
    assert sum(f.max_points for f in h.factors) == 100


def test_format_duration():
    assert format_duration(27) == "27s"
    assert format_duration(207) == "3m 27s"
    assert format_duration(3661) == "1h 1m 1s"


# --- incident creation ----------------------------------------------------
def test_gateway_failure_opens_one_incident_with_evidence(engine, db_path):
    eng, reg = engine
    reg.simulator.set_scenario("gateway")
    eng.run_cycle()

    incs = _open(db_path)
    assert len(incs) == 1
    inc = incs[0]
    assert inc["rule_name"] == "gateway_failure"
    assert inc["priority"] == "Critical"
    assert inc["confidence"] == 95
    assert inc["health_at_start"] < 40

    with connection(db_path) as c:
        devs = {d["name"] for d in m.incident_devices(c, inc["id"])}
        events = m.diagnostic_events(c, inc["id"])
    assert {"PC-01", "PC-02", "PC-03"} <= devs
    kinds = {e["rule_name"] for e in events}
    assert {"incident_opened", "confidence_score", "health_score"} <= kinds


def test_repeated_fault_does_not_duplicate_incident(engine, db_path):
    eng, reg = engine
    reg.simulator.set_scenario("gateway")
    eng.run_cycle()
    eng.run_cycle()
    eng.run_cycle()
    assert len(_open(db_path)) == 1


def test_flap_suppression(app, db_path):
    """With FAILURE_CONFIRM_CYCLES=2 a single bad cycle must not open an incident."""
    app.config["FAILURE_CONFIRM_CYCLES"] = 2
    from ang.incidents.manager import IncidentManager
    eng = app.extensions["ang_engine"]
    eng.incident_manager = IncidentManager(app.config)
    reg = app.extensions["ang_registry"]

    reg.simulator.set_scenario("device")
    eng.run_cycle()
    assert _open(db_path) == []           # pending, not opened
    eng.run_cycle()
    assert len(_open(db_path)) == 1       # confirmed


# --- recovery auto-close (PRD 19) --------------------------------------
def test_recovery_closes_incident_after_two_clean_cycles(engine, db_path):
    eng, reg = engine
    reg.simulator.set_scenario("gateway")
    eng.run_cycle()
    assert len(_open(db_path)) == 1

    reg.simulator.set_scenario("recovery")   # observation reads healthy
    eng.run_cycle()
    assert len(_open(db_path)) == 1           # 1/2 - not yet
    eng.run_cycle()
    assert _open(db_path) == []               # 2/2 - closed

    inc = _all(db_path)[0]
    assert inc["status"] == "resolved"
    assert inc["resolved_at"] is not None
    assert inc["duration"]
    with connection(db_path) as c:
        kinds = {e["rule_name"] for e in m.diagnostic_events(c, inc["id"])}
    assert "recovery_confirmed" in kinds


def test_new_fault_supersedes_previous_incident(engine, db_path):
    eng, reg = engine
    reg.simulator.set_scenario("gateway")
    eng.run_cycle()
    reg.simulator.set_scenario("dns")
    eng.run_cycle()
    eng.run_cycle()

    incs = {i["rule_name"]: i for i in _all(db_path)}
    assert incs["gateway_failure"]["status"] == "resolved"
    assert incs["dns_failure"]["status"] == "open"


# --- API -----------------------------------------------------------------
def test_incident_api_shapes(client, app):
    app.extensions["ang_registry"].simulator.set_scenario("gateway")
    app.extensions["ang_engine"].run_cycle()

    lst = client.get("/api/incidents").get_json()
    assert lst["open_count"] == 1
    inc = lst["incidents"][0]
    assert inc["code"] == "INC-001"
    assert inc["affected"]

    detail = client.get(f"/api/incidents/{inc['id']}").get_json()
    assert detail["timeline"]
    assert detail["affected_devices"][0]["reason"]

    health = client.get("/api/health").get_json()
    assert health["health"]["score"] < 40
    assert health["active_incidents"] == 1
    assert health["health"]["reasons"]

    events = client.get("/api/events").get_json()
    assert events["events"]
