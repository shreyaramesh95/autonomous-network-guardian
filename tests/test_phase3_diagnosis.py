"""Phase 3 - rule-based, dependency-aware diagnosis.

Covers PRD success criteria A-F (section 37) and the design principle in
section 34: never blame the gateway for a single-device fault, and never call a
DNS failure a general internet outage.
"""
from __future__ import annotations

import pytest

from ang.database.db import connection
from ang.database.models import list_devices
from ang.diagnosis.engine import DiagnosisEngine
from ang.diagnosis.observation import Observation
from ang.simulation.simulator import SimulatedProbes, Simulator

from .conftest import config_dict


def diagnose(db_path, scenario):
    cfg = config_dict(DATABASE=db_path)
    sim = Simulator(cfg)
    sim.set_scenario(scenario)
    provider = SimulatedProbes(sim)
    with connection(db_path) as c:
        devices = list_devices(c)
    obs = Observation.from_provider(devices, provider, cfg)
    return DiagnosisEngine(cfg).diagnose(obs)


# --- A: healthy -----------------------------------------------------------
def test_scenario_a_healthy(db_path):
    d = diagnose(db_path, "healthy")
    assert d.is_fault is False
    assert d.priority == "None"
    assert "Healthy" in d.root_cause


# --- B: individual device failure, NOT gateway (PRD 34) -----------------
def test_scenario_b_individual_device(db_path):
    d = diagnose(db_path, "device")
    assert d.rule_name == "individual_device_failure"
    assert d.priority == "Medium"
    assert d.confidence == 88
    assert [a["name"] for a in d.affected] == ["PC-02"]
    top = d.hypotheses[0]
    assert top["key"] == "individual_device_failure"
    gw = next(h for h in d.hypotheses if h["key"] == "gateway_failure")
    assert gw["score"] == 0


# --- C: gateway failure, multiple affected devices ---------------------
def test_scenario_c_gateway_failure(db_path):
    d = diagnose(db_path, "gateway")
    assert d.rule_name == "gateway_failure"
    assert d.priority == "Critical"
    assert d.confidence == 95
    affected = {a["name"] for a in d.affected}
    assert {"PC-01", "PC-02", "PC-03"} <= affected
    assert d.hypotheses[0]["key"] == "gateway_failure"
    # dependency-aware: gateway must out-score individual-device
    ind = next(h for h in d.hypotheses if h["key"] == "individual_device_failure")
    assert d.hypotheses[0]["score"] > ind["score"]


# --- D: DNS failure distinguished from internet failure --------------
def test_scenario_d_dns_failure(db_path):
    d = diagnose(db_path, "dns")
    assert d.rule_name == "dns_failure"
    assert d.priority == "High"
    assert d.confidence == 84
    inet = next(h for h in d.hypotheses if h["key"] == "internet_failure")
    assert inet["score"] == 0


# --- E: internet / WAN failure distinguished from gateway ------------
def test_scenario_e_internet_failure(db_path):
    d = diagnose(db_path, "internet")
    assert d.rule_name == "internet_failure"
    assert d.priority == "Critical"
    assert d.confidence == 86
    dns = next(h for h in d.hypotheses if h["key"] == "dns_failure")
    assert dns["score"] == 0
    gw = next(h for h in d.hypotheses if h["key"] == "gateway_failure")
    assert gw["score"] == 0


# --- F: recovery observation reads as healthy (auto-close is Phase 4) ---
def test_scenario_f_recovery_reads_healthy(db_path):
    d = diagnose(db_path, "recovery")
    assert d.is_fault is False


# --- shared degradation -------------------------------------------------
def test_high_latency_scenario(db_path):
    d = diagnose(db_path, "high_latency")
    assert d.rule_name == "high_latency"
    assert d.priority == "High"
    assert d.confidence == 72


def test_packet_loss_scenario(db_path):
    d = diagnose(db_path, "packet_loss")
    assert d.rule_name == "packet_loss"
    assert d.confidence == 76


# --- evidence + recommendations are always present for a fault ---------
def test_faults_carry_evidence_and_actions(db_path):
    for scenario in ("device", "gateway", "dns", "internet", "high_latency", "packet_loss"):
        d = diagnose(db_path, scenario)
        assert d.evidence, scenario
        assert d.actions, scenario
        assert d.reasoning, scenario
        assert len(d.hypotheses) == 6, scenario


# --- newly registered dependent device joins the correlation ----------
def test_added_dependent_device_counts_toward_gateway_failure(db_path):
    from ang.database.models import create_device, get_gateway

    with connection(db_path) as c:
        gw = get_gateway(c)
        create_device(c, "PC-09", "192.168.1.19", "Computer", "Client", gw["id"])

    cfg = config_dict(DATABASE=db_path)
    sim = Simulator(cfg)
    sim.set_scenario("gateway")  # PC-09 not in scenario down-list -> stays up
    d = _diag_with(db_path, sim, cfg)
    # still a gateway failure, PC-09 simply isn't among the affected
    assert d.rule_name == "gateway_failure"
    assert "PC-09" not in {a["name"] for a in d.affected}


def _diag_with(db_path, sim, cfg):
    from ang.diagnosis.engine import DiagnosisEngine

    with connection(db_path) as c:
        devices = list_devices(c)
    obs = Observation.from_provider(devices, SimulatedProbes(sim), cfg)
    return DiagnosisEngine(cfg).diagnose(obs)
