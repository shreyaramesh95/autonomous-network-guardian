"""Incident endpoints (PRD 17-20, 24.4, 26)."""
from __future__ import annotations

from flask import Blueprint, jsonify

from ..database import models as m
from ..database.db import get_db
from ..incidents.manager import incident_code

bp = Blueprint("incidents", __name__, url_prefix="/api")


def _summary(conn, row) -> dict:
    devices = m.incident_devices(conn, row["id"])
    return {
        "id": row["id"],
        "code": incident_code(row["id"]),
        "root_cause": row["root_cause"],
        "rule_name": row["rule_name"],
        "confidence": row["confidence"],
        "priority": row["priority"],
        "status": row["status"],
        "started_at": row["started_at"],
        "resolved_at": row["resolved_at"],
        "duration": row["duration"],
        "health_at_start": row["health_at_start"],
        "affected": [d["name"] for d in devices],
        "affected_devices": [
            {"name": d["name"], "ip": d["ip_address"], "reason": d["reason"]}
            for d in devices
        ],
    }


@bp.get("/incidents")
def list_incidents():
    conn = get_db()
    rows = m.list_incidents(conn)
    incidents = [_summary(conn, r) for r in rows]
    return jsonify({
        "incidents": incidents,
        "active": [i for i in incidents if i["status"] == "open"],
        "open_count": sum(1 for i in incidents if i["status"] == "open"),
    })


@bp.get("/incidents/<int:incident_id>")
def get_incident(incident_id: int):
    conn = get_db()
    row = m.get_incident(conn, incident_id)
    if row is None:
        return jsonify({"error": "incident not found"}), 404
    data = _summary(conn, row)
    data["timeline"] = [
        {"timestamp": e["timestamp"], "rule_name": e["rule_name"],
         "evidence": e["evidence"]}
        for e in m.diagnostic_events(conn, incident_id)
    ]
    return jsonify(data)


@bp.get("/events")
def recent_events():
    conn = get_db()
    rows = m.recent_diagnostic_events(conn, 40)
    return jsonify({
        "events": [
            {"timestamp": e["timestamp"], "rule_name": e["rule_name"],
             "evidence": e["evidence"],
             "incident_id": e["incident_id"],
             "incident_code": incident_code(e["incident_id"]) if e["incident_id"] else None}
            for e in rows
        ]
    })
