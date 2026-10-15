"""Aggregate dashboard endpoint (PRD 24.1, 30 step 13).

One call returns everything the dashboard header + body need, so the frontend
polls a single URL each monitoring cycle.
"""
from __future__ import annotations

from flask import Blueprint, current_app, jsonify

from ..database import models as m
from ..database.db import get_db
from ..diagnosis.engine import DiagnosisEngine
from ..diagnosis.observation import Observation
from ..incidents.health import compute_health
from ..incidents.manager import incident_code
from ..monitoring.ping_monitor import classify_latency
from . import current_engine, current_registry
from .incidents import _summary

bp = Blueprint("dashboard_api", __name__, url_prefix="/api")


def _device_view(d, latest, cfg) -> dict:
    row = latest.get(d["id"])
    lat = row["latency"] if row else None
    return {
        "id": d["id"], "name": d["name"], "ip_address": d["ip_address"],
        "device_type": d["device_type"], "role": d["role"], "status": d["status"],
        "depends_on": d["depends_on"],
        "latency_ms": lat, "latency_class": classify_latency(lat, cfg),
        "packet_loss_pct": row["packet_loss"] if row else None,
        "reachable": bool(row["reachable"]) if row else None,
        "last_checked": row["timestamp"] if row else None,
    }


@bp.get("/dashboard")
def dashboard():
    engine = current_engine()
    registry = current_registry()
    conn = get_db()
    cfg = current_app.config

    devices = m.list_devices(conn)
    latest = m.latest_measurements(conn)
    device_views = [_device_view(d, latest, cfg) for d in devices]

    # diagnosis + health: use cached values, else compute now
    if engine.latest_diagnosis is not None:
        diag = engine.latest_diagnosis.to_dict()
        health = engine.latest_health.to_dict()
    else:
        obs = Observation.from_db(conn)
        diag = DiagnosisEngine(cfg).diagnose(obs).to_dict()
        health = compute_health(obs, cfg).to_dict()

    gw = m.get_gateway(conn)
    gw_view = next((v for v in device_views if gw and v["id"] == gw["id"]), None)
    dns = m.latest_service_check(conn, "dns")
    inet = m.latest_service_check(conn, "internet")
    dns_ok = bool(dns["reachable"]) if dns else True
    inet_ok = bool(inet["reachable"]) if inet else True
    gw_ok = (gw_view["status"] in ("online", "degraded")) if gw_view else True

    shared = [
        {"name": f"Gateway {gw['name']}" if gw else "Gateway", "ok": gw_ok,
         "state": "Online" if gw_ok else "Failed"},
        {"name": "DNS resolution", "ok": dns_ok,
         "state": "Resolving" if dns_ok else "Failed"},
        {"name": "Internet / WAN", "ok": inet_ok,
         "state": "Reachable" if inet_ok else "Failed"},
    ]

    clients = [v for v in device_views if v["role"] in ("Client", "Service", "Peripheral")]
    all_incidents = m.list_incidents(conn)
    active = [_summary(conn, r) for r in all_incidents if r["status"] == "open"]
    last_resolved = next((r for r in all_incidents if r["status"] == "resolved"), None)

    graph_data = _build_topology_graph(device_views, gw, gw_view, gw_ok, dns_ok, inet_ok, diag)

    return jsonify({
        "monitoring": engine.status(),
        "scenario": registry.describe(),
        "health": health,
        "devices": {
            "online": sum(1 for v in device_views if v["status"] == "online"),
            "total": len(device_views),
            "list": device_views,
        },
        "shared_dependencies": shared,
        "topology": {
            "clients": [{"name": c["name"], "status": c["status"]} for c in clients[:3]],
            "gateway": {"name": gw["name"] if gw else None, "ok": gw_ok},
            "internet": {"ok": inet_ok},
            "note": _topology_note(conn, gw),
            "graph": graph_data,
        },
        "diagnosis": diag,
        "active_incidents": active,
        "recent_events": _recent_events(conn, engine, device_views, health),
        "last_recovery": last_resolved["duration"] if last_resolved else None,
    })


@bp.get("/topology")
def topology_data():
    conn = get_db()
    cfg = current_app.config
    engine = current_engine()
    registry = current_registry()

    devices = m.list_devices(conn)
    latest = m.latest_measurements(conn)
    device_views = [_device_view(d, latest, cfg) for d in devices]

    if engine.latest_diagnosis is not None:
        diag = engine.latest_diagnosis.to_dict()
        health = engine.latest_health.to_dict()
    else:
        obs = Observation.from_db(conn)
        diag = DiagnosisEngine(cfg).diagnose(obs).to_dict()
        health = compute_health(obs, cfg).to_dict()

    gw = m.get_gateway(conn)
    gw_view = next((v for v in device_views if gw and v["id"] == gw["id"]), None)
    dns = m.latest_service_check(conn, "dns")
    inet = m.latest_service_check(conn, "internet")
    dns_ok = bool(dns["reachable"]) if dns else True
    inet_ok = bool(inet["reachable"]) if inet else True
    gw_ok = (gw_view["status"] in ("online", "degraded")) if gw_view else True

    graph_data = _build_topology_graph(device_views, gw, gw_view, gw_ok, dns_ok, inet_ok, diag)

    return jsonify({
        "health": health,
        "diagnosis": diag,
        "scenario": registry.describe(),
        "graph": graph_data,
        "note": _topology_note(conn, gw),
        "devices": device_views,
        "gateway": gw_view,
    })


def _build_topology_graph(device_views, gw, gw_view, gw_ok, dns_ok, inet_ok, diag) -> dict:
    nodes = []
    links = []

    rule_name = diag.get("rule_name", "")
    root_cause_str = diag.get("root_cause", "")
    affected_names = {a["name"] for a in diag.get("affected", [])} if isinstance(diag.get("affected"), list) else set()

    # Tier 0: External Cloud / WAN & DNS
    nodes.append({
        "id": "wan_internet",
        "name": "Internet / WAN",
        "type": "Cloud",
        "role": "External",
        "status": "online" if inet_ok else "offline",
        "ip_address": "1.1.1.1",
        "tier": 0,
        "is_root_cause": (rule_name == "internet_failure"),
        "is_affected": False,
    })

    nodes.append({
        "id": "service_dns",
        "name": "DNS Resolver",
        "type": "Service",
        "role": "DNS",
        "status": "online" if dns_ok else "offline",
        "ip_address": "8.8.8.8",
        "tier": 0,
        "is_root_cause": (rule_name == "dns_failure"),
        "is_affected": False,
    })

    # Tier 1: Gateway Router
    if gw:
        is_gw_rc = (rule_name == "gateway_failure")
        nodes.append({
            "id": f"dev_{gw['id']}",
            "device_id": gw["id"],
            "name": gw["name"],
            "type": gw["device_type"],
            "role": gw["role"],
            "status": gw_view["status"] if gw_view else "unknown",
            "ip_address": gw["ip_address"],
            "latency_ms": gw_view["latency_ms"] if gw_view else None,
            "packet_loss_pct": gw_view["packet_loss_pct"] if gw_view else None,
            "tier": 1,
            "is_root_cause": is_gw_rc,
            "is_affected": False,
        })
        links.append({"source": f"dev_{gw['id']}", "target": "wan_internet", "label": "WAN Uplink", "ok": inet_ok and gw_ok})
        links.append({"source": f"dev_{gw['id']}", "target": "service_dns", "label": "DNS Lookup", "ok": dns_ok and gw_ok})

    # Tier 2: LAN Endpoints
    for d in device_views:
        if gw and d["id"] == gw["id"]:
            continue
        is_rc = (rule_name == "single_device_failure" and d["name"] in root_cause_str)
        is_aff = (d["name"] in affected_names) or (rule_name == "gateway_failure")
        nodes.append({
            "id": f"dev_{d['id']}",
            "device_id": d["id"],
            "name": d["name"],
            "type": d["device_type"],
            "role": d["role"],
            "status": d["status"],
            "ip_address": d["ip_address"],
            "latency_ms": d["latency_ms"],
            "packet_loss_pct": d["packet_loss_pct"],
            "depends_on": d["depends_on"],
            "tier": 2,
            "is_root_cause": is_rc,
            "is_affected": is_aff and not is_rc,
        })
        parent_id = d["depends_on"] if d["depends_on"] else (gw["id"] if gw else None)
        if parent_id:
            links.append({
                "source": f"dev_{d['id']}",
                "target": f"dev_{parent_id}",
                "label": "LAN Access",
                "ok": (d["status"] in ("online", "degraded")),
            })

    return {
        "nodes": nodes,
        "links": links,
        "rule_name": rule_name,
        "root_cause": root_cause_str,
        "priority": diag.get("priority", "None"),
        "confidence": diag.get("confidence", 0),
        "blast_radius_count": len(affected_names),
    }


def _topology_note(conn, gw) -> str:
    if not gw:
        return ""
    deps = conn.execute(
        "SELECT name FROM devices WHERE depends_on = ? AND role = 'Client' ORDER BY name",
        (gw["id"],),
    ).fetchall()
    names = [r["name"] for r in deps]
    if not names:
        return ""
    return f"{', '.join(names)} share {gw['name']} as their only route out."


def _recent_events(conn, engine, device_views, health) -> list[dict]:
    events: list[dict] = []
    online = sum(1 for v in device_views if v["reachable"])
    total = len(device_views)
    if engine.last_cycle_at:
        events.append({"t": engine.last_cycle_at,
                       "text": f"Monitoring cycle complete — {online}/{total} reachable"})
        events.append({"t": engine.last_cycle_at,
                       "text": f"Health score {health['score']} / 100 ({health['status']})"})
    for e in m.recent_diagnostic_events(conn, 12):
        code = incident_code(e["incident_id"]) if e["incident_id"] else "—"
        events.append({"t": e["timestamp"], "text": f"{code}: {e['evidence']}"})
    return events[:14]
