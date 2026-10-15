"""Phase 1 - probe seam, monitoring cycle, measurement storage."""
from __future__ import annotations

import pytest

from ang.database.db import connection
from ang.monitoring.engine import MonitoringEngine
from ang.monitoring.ping_monitor import classify_latency, status_from_probe
from ang.monitoring.probes import ProbeProvider, ProbeResult, ServiceResult
from ang.monitoring.registry import ProviderRegistry

from .conftest import config_dict


class StubProvider(ProbeProvider):
    """Fixed responses - proves the engine never calls the network itself."""

    def __init__(self, down=(), dns_ok=True, internet_ok=True):
        self.down = set(down)
        self.dns_ok = dns_ok
        self.internet_ok = internet_ok

    def probe_device(self, ip):
        if ip in self.down:
            return ProbeResult(False, None, 100.0)
        return ProbeResult(True, 12.0, 0.0)

    def check_dns(self, hostname):
        return ServiceResult(self.dns_ok, 10.0, "stub dns")

    def check_internet(self, ip, port):
        return ServiceResult(self.internet_ok, 15.0, "stub internet")


@pytest.fixture()
def engine(cfg):
    registry = ProviderRegistry(cfg)
    return MonitoringEngine(cfg, registry), registry


def test_latency_classification_matches_prd_table():
    c = {"LATENCY_GOOD_MS": 50, "LATENCY_MODERATE_MS": 100, "LATENCY_HIGH_MS": 200}
    assert classify_latency(20, c) == "good"
    assert classify_latency(75, c) == "moderate"
    assert classify_latency(150, c) == "high"
    assert classify_latency(250, c) == "critical"
    assert classify_latency(None, c) is None


def test_status_from_probe():
    c = {"LATENCY_GOOD_MS": 50, "LATENCY_MODERATE_MS": 100,
         "LATENCY_HIGH_MS": 200, "PACKET_LOSS_THRESHOLD_PCT": 15}
    assert status_from_probe(ProbeResult(True, 10, 0), c) == "online"
    assert status_from_probe(ProbeResult(False, None, 100), c) == "offline"
    assert status_from_probe(ProbeResult(True, 10, 40), c) == "degraded"
    assert status_from_probe(ProbeResult(True, 250, 0), c) == "degraded"


def test_cycle_stores_measurements_and_service_checks(engine):
    eng, registry = engine
    registry.current = lambda: StubProvider()

    eng.run_cycle()

    with connection(eng.db_path) as c:
        n = c.execute("SELECT COUNT(*) AS n FROM measurements").fetchone()["n"]
        services = {r["service"] for r in c.execute("SELECT DISTINCT service FROM service_checks")}
    assert n == 6
    assert services == {"dns", "internet"}


def test_cycle_updates_device_status_and_caches_diagnosis(engine):
    eng, registry = engine
    registry.current = lambda: StubProvider(down={"192.168.1.11"})

    diagnosis = eng.run_cycle()

    with connection(eng.db_path) as c:
        statuses = {r["name"]: r["status"]
                    for r in c.execute("SELECT name, status FROM devices")}
    assert statuses["PC-02"] == "offline"
    assert statuses["PC-01"] == "online"
    assert eng.latest_diagnosis is diagnosis
    assert eng.last_cycle_at is not None
    assert eng.cycle_count == 1


def test_two_cycles_keep_history(engine):
    eng, registry = engine
    registry.current = lambda: StubProvider()
    eng.run_cycle()
    eng.run_cycle()
    with connection(eng.db_path) as c:
        n = c.execute("SELECT COUNT(*) AS n FROM measurements").fetchone()["n"]
    assert n == 12
