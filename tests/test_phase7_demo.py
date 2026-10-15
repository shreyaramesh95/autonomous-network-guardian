"""Phase 7 - the full demonstration workflow end to end over the HTTP API
(PRD 23 / 37 success criteria A-F)."""
from __future__ import annotations

import pytest


@pytest.fixture()
def demo(client, app):
    def apply(action):
        return client.post(f"/api/simulation/{action}").get_json()
    def cycle():
        client.post("/api/monitoring/cycle")
    def health():
        return client.get("/api/health").get_json()
    def incidents():
        return client.get("/api/incidents").get_json()
    client.post("/api/monitoring/reset-data")
    return type("Demo", (), dict(apply=staticmethod(apply), cycle=staticmethod(cycle),
                                 health=staticmethod(health), incidents=staticmethod(incidents)))


def test_scenario_a_healthy(demo):
    d = demo.apply("reset")
    assert d["diagnosis"]["is_fault"] is False
    h = demo.health()
    assert h["health"]["score"] >= 95
    assert h["active_incidents"] == 0


def test_scenario_b_individual_device_not_gateway(demo):
    d = demo.apply("device-failure")
    assert d["diagnosis"]["rule_name"] == "individual_device_failure"
    assert demo.incidents()["incidents"][0]["priority"] == "Medium"


def test_scenario_c_gateway_lists_multiple_devices(demo):
    d = demo.apply("gateway-failure")
    diag = d["diagnosis"]
    assert diag["rule_name"] == "gateway_failure"
    assert len({a["name"] for a in diag["affected"]}) >= 3
    assert demo.health()["health"]["status"] == "CRITICAL"


def test_scenario_d_dns_not_internet(demo):
    d = demo.apply("dns-failure")
    assert d["diagnosis"]["rule_name"] == "dns_failure"
    inet = next(h for h in d["diagnosis"]["hypotheses"] if h["key"] == "internet_failure")
    assert inet["score"] == 0


def test_scenario_e_internet_not_gateway(demo):
    d = demo.apply("internet-failure")
    assert d["diagnosis"]["rule_name"] == "internet_failure"
    gw = next(h for h in d["diagnosis"]["hypotheses"] if h["key"] == "gateway_failure")
    assert gw["score"] == 0


def test_scenario_f_recovery_full_cycle(demo):
    demo.apply("gateway-failure")
    assert demo.incidents()["open_count"] == 1

    demo.apply("recovery")          # applies + 1 cycle
    assert demo.incidents()["open_count"] == 1   # 1/2
    demo.cycle()                                  # 2/2
    inc = demo.incidents()["incidents"][0]
    assert inc["status"] == "resolved"
    assert inc["resolved_at"] and inc["duration"]

    assert demo.health()["health"]["score"] >= 95


def test_full_demo_sequence_leaves_consistent_history(demo):
    for action in ("device-failure", "recovery", "recovery",
                   "gateway-failure", "recovery", "recovery",
                   "dns-failure", "recovery", "recovery"):
        demo.apply(action)
    data = demo.incidents()
    assert data["open_count"] == 0
    assert len(data["incidents"]) == 3
    assert all(i["status"] == "resolved" for i in data["incidents"])
    assert all(i["duration"] for i in data["incidents"])
