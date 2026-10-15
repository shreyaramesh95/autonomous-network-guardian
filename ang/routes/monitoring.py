"""Monitoring status, current diagnosis, and health liveness (PRD 26)."""
from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from ..database.db import get_db
from ..diagnosis.engine import DiagnosisEngine
from ..diagnosis.observation import Observation
from ..incidents.health import compute_health
from . import current_engine, current_registry

bp = Blueprint("monitoring", __name__, url_prefix="/api")


def _latest_diagnosis() -> dict:
    engine = current_engine()
    if engine.latest_diagnosis is not None:
        return engine.latest_diagnosis.to_dict()
    # Nothing cached yet (e.g. tests, or before the first cycle): compute now.
    conn = get_db()
    obs = Observation.from_db(conn)
    return DiagnosisEngine(current_app.config).diagnose(obs).to_dict()


def _latest_health() -> dict:
    engine = current_engine()
    if engine.latest_health is not None:
        return engine.latest_health.to_dict()
    obs = Observation.from_db(get_db())
    return compute_health(obs, current_app.config).to_dict()


@bp.get("/monitoring")
def monitoring_status():
    return jsonify(current_engine().status())


@bp.post("/monitoring/cycle")
def force_cycle():
    """Run one monitoring cycle immediately (demo aid)."""
    diagnosis = current_engine().run_cycle()
    return jsonify({"ran": True, "diagnosis": diagnosis.to_dict()})


@bp.post("/monitoring/mode")
def set_mode():
    data = request.get_json(silent=True) or {}
    mode = data.get("mode", "")
    try:
        current_registry().set_mode(mode)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(current_registry().describe())


@bp.get("/diagnosis")
def get_diagnosis():
    return jsonify(_latest_diagnosis())


@bp.post("/monitoring/reset-data")
def reset_data():
    """Wipe measurements + incident history and return to a healthy baseline.

    Devices are kept. Handy for starting a clean demo.
    """
    conn = get_db()
    for table in ("diagnostic_events", "incident_devices", "incidents",
                  "service_checks", "measurements"):
        conn.execute(f"DELETE FROM {table}")
    conn.execute("UPDATE devices SET status = 'unknown'")
    conn.commit()

    engine = current_engine()
    engine.incident_manager._pending.clear()
    engine.latest_diagnosis = None
    engine.latest_health = None
    engine.latest_observation = None
    engine.latest_incident_sync = None
    current_registry().simulator.set_scenario("healthy")
    return jsonify({"reset": True, "scenario": current_registry().describe()})


@bp.get("/health")
def health():
    """Network health score (0-100, PRD 21) plus device counts, current
    diagnosis summary and open-incident count - everything the dashboard header
    needs in one call."""
    engine = current_engine()
    conn = get_db()
    from ..database import models as m

    devices = m.list_devices(conn)
    online = sum(1 for d in devices if d["status"] == "online")
    diag = _latest_diagnosis()
    health_score = _latest_health()
    open_count = len(m.open_incidents(conn))

    return jsonify({
        "status": "ok",
        "health": health_score,
        "monitoring": engine.status(),
        "devices": {"online": online, "total": len(devices)},
        "active_incidents": open_count,
        "diagnosis": {
            "root_cause": diag["root_cause"],
            "priority": diag["priority"],
            "confidence": diag["confidence"],
            "is_fault": diag["is_fault"],
        },
    })


@bp.get("/health/score")
def health_score():
    return jsonify(_latest_health())
