"""Runtime simulation state + the SimulatedProbes provider (PRD 22)."""
from __future__ import annotations

from ..monitoring.probes import ProbeProvider, ProbeResult, ServiceResult
from .scenarios import (
    BASE_LATENCY_MS,
    DEFAULT_BASE_LATENCY_MS,
    DEFAULT_LOSS_PCT,
    LOSS_PATTERN_PCT,
    SCENARIOS,
    Scenario,
)


class Simulator:
    """Holds the currently active scenario. In-memory and process-local -
    scenarios are meant to be re-selected each demo, not persisted."""

    def __init__(self, config):
        self._config = config
        initial = (config.get("INITIAL_SCENARIO", "healthy")
                   if hasattr(config, "get") else config["INITIAL_SCENARIO"])
        self.scenario_key = initial if initial in SCENARIOS else "healthy"

    @property
    def scenario(self) -> Scenario:
        return SCENARIOS[self.scenario_key]

    def set_scenario(self, key: str) -> Scenario:
        if key not in SCENARIOS:
            raise ValueError(f"unknown scenario: {key!r}")
        self.scenario_key = key
        return self.scenario

    # -- probe results -------------------------------------------------------
    def device_result(self, ip: str) -> ProbeResult:
        sc = self.scenario
        if ip in sc.down_ips:
            return ProbeResult(reachable=False, latency_ms=None, packet_loss_pct=100.0)

        base = BASE_LATENCY_MS.get(ip, DEFAULT_BASE_LATENCY_MS)
        if sc.degrade == "latency":
            # mockup formula: base * 16 + 40
            return ProbeResult(reachable=True, latency_ms=float(base * 16 + 40),
                               packet_loss_pct=0.0)
        if sc.degrade == "loss":
            loss = float(LOSS_PATTERN_PCT.get(ip, DEFAULT_LOSS_PCT))
            return ProbeResult(reachable=True, latency_ms=float(base), packet_loss_pct=loss)
        return ProbeResult(reachable=True, latency_ms=float(base), packet_loss_pct=0.0)

    def dns_result(self) -> ServiceResult:
        sc = self.scenario
        if sc.dns_ok:
            return ServiceResult(reachable=True, latency_ms=14.0,
                                 detail=f"{self._hostname()} resolved (simulated)")
        return ServiceResult(reachable=False,
                             detail=f"{self._hostname()} SERVFAIL (simulated)")

    def internet_result(self) -> ServiceResult:
        sc = self.scenario
        ip = self._internet_ip()
        if sc.internet_ok:
            return ServiceResult(reachable=True, latency_ms=18.0,
                                 detail=f"{ip} reachable (simulated)")
        return ServiceResult(reachable=False, detail=f"{ip} unreachable (simulated)")

    # -- helpers -----------------------------------------------------------
    def _hostname(self) -> str:
        c = self._config
        return c.get("DNS_TEST_HOSTNAME", "example.com") if hasattr(c, "get") else c["DNS_TEST_HOSTNAME"]

    def _internet_ip(self) -> str:
        c = self._config
        return c.get("INTERNET_TEST_IP", "1.1.1.1") if hasattr(c, "get") else c["INTERNET_TEST_IP"]


class SimulatedProbes(ProbeProvider):
    def __init__(self, simulator: Simulator):
        self.simulator = simulator

    def probe_device(self, ip: str) -> ProbeResult:
        return self.simulator.device_result(ip)

    def check_dns(self, hostname: str) -> ServiceResult:
        return self.simulator.dns_result()

    def check_internet(self, ip: str, port: int) -> ServiceResult:
        return self.simulator.internet_result()
