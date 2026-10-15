"""Simulation control (PRD 22, 26).

POST /api/simulation/<action> selects a deterministic scenario. The next
monitoring cycle (or POST /api/monitoring/cycle) then observes it.
"""
from __future__ import annotations

from flask import Blueprint, jsonify

from ..simulation.scenarios import ENDPOINT_TO_KEY, SCENARIOS
from . import current_engine, current_registry

bp = Blueprint("simulation", __name__, url_prefix="/api/simulation")


def _state() -> dict:
    reg = current_registry()
    sim = reg.simulator
    return {
        "mode": reg.mode,
        "active": sim.scenario_key,
        "label": sim.scenario.label,
        "note": sim.scenario.note,
        "scenarios": [
            {"key": s.key, "label": s.label, "note": s.note,
             "endpoint": f"/api/simulation/{ep}"}
            for ep, k in ENDPOINT_TO_KEY.items()
            for s in [SCENARIOS[k]]
        ],
    }


@bp.get("")
@bp.get("/")
def get_state():
    return jsonify(_state())


@bp.post("/<action>")
def run_scenario(action: str):
    key = ENDPOINT_TO_KEY.get(action)
    if key is None:
        return jsonify({
            "error": f"unknown scenario '{action}'",
            "valid": sorted(ENDPOINT_TO_KEY),
        }), 404

    reg = current_registry()
    reg.simulator.set_scenario(key)
    if reg.mode != "simulation":
        reg.set_mode("simulation")

    # Observe the new scenario right away so the response is immediately useful.
    diagnosis = current_engine().run_cycle()
    return jsonify({
        "applied": key,
        "state": _state(),
        "diagnosis": diagnosis.to_dict(),
    })
