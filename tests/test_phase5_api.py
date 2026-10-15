"""Phase 5 - complete REST surface for the frontend."""
from __future__ import annotations

import pytest

PRD_ENDPOINTS = [
    ("GET", "/api/devices"),
    ("GET", "/api/health"),
    ("GET", "/api/incidents"),
    ("GET", "/api/diagnosis"),
]


@pytest.mark.parametrize("method,path", PRD_ENDPOINTS)
def test_prd_endpoints_exist(client, method, path):
    assert client.open(path, method=method).status_code == 200


def test_dashboard_aggregate_has_everything_the_page_needs(client, app):
    app.extensions["ang_registry"].simulator.set_scenario("gateway")
    app.extensions["ang_engine"].run_cycle()

    d = client.get("/api/dashboard").get_json()
    for key in ("monitoring", "scenario", "health", "devices", "shared_dependencies",
                "topology", "diagnosis", "active_incidents", "recent_events"):
        assert key in d, key
    assert d["devices"]["total"] == 6
    assert len(d["shared_dependencies"]) == 3
    assert d["health"]["score"] < 40
    assert d["diagnosis"]["rule_name"] == "gateway_failure"
    assert d["active_incidents"][0]["code"] == "INC-001"
    assert d["topology"]["note"]


def test_device_options_endpoint(client):
    d = client.get("/api/devices/options").get_json()
    assert {"dependency_options", "device_types", "roles", "suggested"} <= set(d)
    assert any(o["role"] == "Gateway" for o in d["dependency_options"])


def test_topology_endpoint(client, app):
    r = client.get("/api/topology")
    assert r.status_code == 200
    d = r.get_json()
    assert "graph" in d
    assert "nodes" in d["graph"]
    assert "links" in d["graph"]
    assert any(n["id"] == "wan_internet" for n in d["graph"]["nodes"])


def test_suggested_device_is_ready_to_save(client):
    """The register dialog pre-fills these; saving them unchanged must work."""
    s = client.get("/api/devices").get_json()["suggested"]
    assert s["name"] and s["name"] not in {"RTR-01", "PC-01", "PC-02", "PC-03"}
    assert s["ip_address"].startswith("192.168.1.")
    r = client.post("/api/devices", json=s)
    assert r.status_code == 201
    # next suggestion must not collide with the one we just saved
    s2 = client.get("/api/devices").get_json()["suggested"]
    assert s2["name"] != s["name"] and s2["ip_address"] != s["ip_address"]


def test_devices_list_carries_dependency_options(client):
    d = client.get("/api/devices").get_json()
    assert len(d["dependency_options"]) == 6


def test_create_device_with_dependency(client):
    r = client.post("/api/devices", json={
        "name": "PC-07", "ip_address": "192.168.1.17",
        "device_type": "Computer", "role": "Client", "depends_on": 1,
    })
    assert r.status_code == 201
    assert r.get_json()["depends_on"] == 1


def test_create_device_validation(client):
    r = client.post("/api/devices", json={"name": "", "device_type": "Toaster"})
    assert r.status_code == 400
    assert r.get_json()["errors"]


def test_reset_data_clears_history_keeps_devices(client, app):
    app.extensions["ang_registry"].simulator.set_scenario("gateway")
    app.extensions["ang_engine"].run_cycle()
    assert client.get("/api/incidents").get_json()["open_count"] == 1

    r = client.post("/api/monitoring/reset-data")
    assert r.status_code == 200
    assert client.get("/api/incidents").get_json()["incidents"] == []
    assert client.get("/api/devices").get_json()["total"] == 6
    assert client.get("/api/simulation").get_json()["active"] == "healthy"


def test_events_endpoint(client, app):
    app.extensions["ang_registry"].simulator.set_scenario("dns")
    app.extensions["ang_engine"].run_cycle()
    assert client.get("/api/events").get_json()["events"]
