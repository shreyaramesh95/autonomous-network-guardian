"""Phase 2 - deterministic simulation scenarios."""
from __future__ import annotations

import pytest

from ang.simulation.scenarios import ENDPOINT_TO_KEY, SCENARIOS
from ang.simulation.simulator import SimulatedProbes, Simulator

from .conftest import config_dict

GW, PC2 = "192.168.1.1", "192.168.1.11"


@pytest.fixture()
def sim():
    return Simulator(config_dict())


def test_all_endpoint_aliases_map_to_real_scenarios():
    for key in ENDPOINT_TO_KEY.values():
        assert key in SCENARIOS


def test_healthy_scenario_everything_up(sim):
    sim.set_scenario("healthy")
    assert sim.device_result(GW).reachable
    assert sim.device_result(PC2).reachable
    assert sim.dns_result().reachable
    assert sim.internet_result().reachable


def test_gateway_scenario_takes_down_clients_and_wan(sim):
    sim.set_scenario("gateway")
    assert sim.device_result(GW).reachable is False
    assert sim.device_result(PC2).reachable is False
    assert sim.device_result("192.168.1.10").reachable is False
    assert sim.dns_result().reachable is False
    assert sim.internet_result().reachable is False


def test_device_scenario_only_pc02_down(sim):
    sim.set_scenario("device")
    assert sim.device_result(PC2).reachable is False
    assert sim.device_result(GW).reachable is True
    assert sim.device_result("192.168.1.10").reachable is True
    assert sim.internet_result().reachable is True


def test_dns_vs_internet_scenarios_differ(sim):
    sim.set_scenario("dns")
    assert sim.dns_result().reachable is False
    assert sim.internet_result().reachable is True  # external IP still reachable

    sim.set_scenario("internet")
    assert sim.dns_result().reachable is False
    assert sim.internet_result().reachable is False


def test_latency_and_loss_scenarios_are_degradations_not_outages(sim):
    sim.set_scenario("high_latency")
    r = sim.device_result("192.168.1.10")  # PC-01, base 8ms -> 8*16+40
    assert r.reachable and r.latency_ms == 168.0 and r.packet_loss_pct == 0.0

    sim.set_scenario("packet_loss")
    r = sim.device_result("192.168.1.11")  # PC-02
    assert r.reachable and r.packet_loss_pct == 40.0


def test_scenarios_are_deterministic(sim):
    sim.set_scenario("high_latency")
    a = sim.device_result("192.168.1.12")
    b = sim.device_result("192.168.1.12")
    assert (a.reachable, a.latency_ms, a.packet_loss_pct) == \
           (b.reachable, b.latency_ms, b.packet_loss_pct)


def test_simulated_probes_provider_delegates(sim):
    sim.set_scenario("gateway")
    p = SimulatedProbes(sim)
    assert p.probe_device(GW).reachable is False
    assert p.check_dns("example.com").reachable is False
    assert p.check_internet("1.1.1.1", 53).reachable is False


def test_unknown_scenario_rejected(sim):
    with pytest.raises(ValueError):
        sim.set_scenario("meltdown")


def test_simulation_endpoints_switch_scenario(client):
    r = client.post("/api/simulation/gateway-failure")
    assert r.status_code == 200
    body = r.get_json()
    assert body["applied"] == "gateway"
    assert body["diagnosis"]["rule_name"] == "gateway_failure"

    r = client.post("/api/simulation/reset")
    assert r.get_json()["applied"] == "healthy"

    r = client.post("/api/simulation/nope")
    assert r.status_code == 404
