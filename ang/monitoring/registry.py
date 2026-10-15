"""Chooses which ProbeProvider the monitoring engine uses right now."""
from __future__ import annotations

from ..simulation.simulator import Simulator, SimulatedProbes
from .live_probes import LiveProbes
from .probes import ProbeProvider

VALID_MODES = ("simulation", "live")


class ProviderRegistry:
    def __init__(self, config):
        self._config = config
        self.simulator = Simulator(config)
        self._live = LiveProbes(config)
        self._simulated = SimulatedProbes(self.simulator)
        mode = config.get("PROBE_MODE", "simulation") if hasattr(config, "get") else config["PROBE_MODE"]
        self.mode = mode if mode in VALID_MODES else "simulation"

    def current(self) -> ProbeProvider:
        return self._simulated if self.mode == "simulation" else self._live

    def set_mode(self, mode: str) -> None:
        if mode not in VALID_MODES:
            raise ValueError(f"unknown probe mode: {mode!r}")
        self.mode = mode

    def describe(self) -> dict:
        sc = self.simulator.scenario
        return {
            "mode": self.mode,
            "scenario": self.simulator.scenario_key,
            "scenario_label": sc.label,
            "scenario_note": sc.note,
        }
