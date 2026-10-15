"""Device registration and listing (PRD 5, 24.2, 26)."""
from __future__ import annotations

import sqlite3

from flask import Blueprint, jsonify, request

from ..database import models as m
from ..database.db import get_db
from ..monitoring import discovery
from ..monitoring.ping_monitor import classify_latency

bp = Blueprint("devices", __name__, url_prefix="/api")

VALID_TYPES = {"Computer", "Router", "Server", "Printer"}
VALID_ROLES = {"Client", "Gateway", "Service", "Peripheral"}


def _device_payload(conn, d, latest) -> dict:
    row = latest.get(d["id"])
    latency = row["latency"] if row else None
    from flask import current_app
    return {
        "id": d["id"],
        "name": d["name"],
        "ip_address": d["ip_address"],
        "device_type": d["device_type"],
        "role": d["role"],
        "status": d["status"],
        "depends_on": d["depends_on"],
        "created_at": d["created_at"],
        "latency_ms": latency,
        "latency_class": classify_latency(latency, current_app.config),
        "packet_loss_pct": row["packet_loss"] if row else None,
        "reachable": bool(row["reachable"]) if row else None,
        "last_checked": row["timestamp"] if row else None,
    }


def _dependency_options(conn) -> list[dict]:
    return [
        {"id": d["id"], "name": d["name"], "ip_address": d["ip_address"],
         "role": d["role"]}
        for d in m.list_devices(conn)
    ]


def _suggested_device(conn) -> dict:
    """A ready-to-save name + IP so the register dialog works on first click."""
    devices = m.list_devices(conn)
    names = {d["name"] for d in devices}
    used_ips = {d["ip_address"] for d in devices}

    name = next((f"PC-{n:02d}" for n in range(1, 100) if f"PC-{n:02d}" not in names), "")

    prefix = "192.168.1."
    gw = m.get_gateway(conn)
    if gw and gw["ip_address"].count(".") == 3:
        prefix = gw["ip_address"].rsplit(".", 1)[0] + "."
    ip = next((f"{prefix}{h}" for h in range(11, 250)
               if f"{prefix}{h}" not in used_ips), "")

    gw_id = gw["id"] if gw else None
    return {"name": name, "ip_address": ip, "device_type": "Computer",
            "role": "Client", "depends_on": gw_id}


@bp.get("/devices")
def list_devices():
    conn = get_db()
    latest = m.latest_measurements(conn)
    devices = [_device_payload(conn, d, latest) for d in m.list_devices(conn)]
    return jsonify({
        "devices": devices,
        "online": sum(1 for d in devices if d["status"] == "online"),
        "total": len(devices),
        "dependency_options": _dependency_options(conn),
        "suggested": _suggested_device(conn),
    })


@bp.get("/devices/options")
def device_options():
    conn = get_db()
    return jsonify({
        "dependency_options": _dependency_options(conn),
        "device_types": sorted(VALID_TYPES),
        "roles": sorted(VALID_ROLES),
        "suggested": _suggested_device(conn),
    })


@bp.get("/devices/<int:device_id>")
def get_device(device_id: int):
    conn = get_db()
    d = m.get_device(conn, device_id)
    if d is None:
        return jsonify({"error": "device not found"}), 404
    latest = m.latest_measurements(conn)
    return jsonify(_device_payload(conn, d, latest))


@bp.post("/devices")
def create_device():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    ip = (data.get("ip_address") or "").strip()
    dtype = (data.get("device_type") or "").strip()
    role = (data.get("role") or "").strip()
    depends_on = data.get("depends_on")

    errors = []
    if not name:
        errors.append("name is required")
    if not ip:
        errors.append("ip_address is required")
    if dtype not in VALID_TYPES:
        errors.append(f"device_type must be one of {sorted(VALID_TYPES)}")
    if role not in VALID_ROLES:
        errors.append(f"role must be one of {sorted(VALID_ROLES)}")

    conn = get_db()
    existing = m.list_devices(conn)
    if depends_on is not None and m.get_device(conn, depends_on) is None:
        errors.append("depends_on must reference an existing device")
    if name and any(d["name"] == name for d in existing):
        errors.append("a device with that name already exists")
    if ip and any(d["ip_address"] == ip for d in existing):
        errors.append("a device with that IP address already exists")
    if errors:
        return jsonify({"errors": errors}), 400

    try:
        device_id = m.create_device(conn, name, ip, dtype, role, depends_on)
        conn.commit()
    except sqlite3.IntegrityError as exc:
        conn.rollback()
        return jsonify({"errors": [f"could not save device: {exc}"]}), 409

    d = m.get_device(conn, device_id)
    return jsonify(_device_payload(conn, d, m.latest_measurements(conn))), 201


@bp.delete("/devices/<int:device_id>")
def remove_device(device_id: int):
    conn = get_db()
    if m.get_device(conn, device_id) is None:
        return jsonify({"error": "device not found"}), 404
    m.delete_device(conn, device_id)
    conn.commit()
    return jsonify({"deleted": device_id})


@bp.get("/devices/discover")
def discover_devices():
    """Ping-sweep the operator's own LAN/Wi-Fi to find real devices to
    register, so monitoring isn't limited to the sample topology."""
    cidr_override = (request.args.get("cidr") or "").strip() or None
    info = discovery.get_network_info(cidr_override)
    if not info.scan_cidr:
        return jsonify({"error": "could not determine a network to scan",
                         "network": info.__dict__}), 400

    hosts = discovery.scan_lan(info.scan_cidr, local_ip=info.local_ip,
                                gateway_ip=info.gateway_ip)

    conn = get_db()
    registered_ips = {d["ip_address"] for d in m.list_devices(conn)}
    discovered = [{
        "ip": h.ip,
        "hostname": h.hostname,
        "mac": h.mac,
        "is_self": h.is_self,
        "is_gateway": h.is_gateway,
        "already_registered": h.ip in registered_ips,
        "suggested_name": ("RTR-WIFI" if h.is_gateway else
                            (h.hostname.split(".")[0] if h.hostname else f"HOST-{h.ip.rsplit('.', 1)[-1]}")),
        "suggested_role": "Gateway" if h.is_gateway else "Client",
        "suggested_type": "Router" if h.is_gateway else "Computer",
    } for h in hosts]

    return jsonify({
        "network": {
            "local_ip": info.local_ip,
            "gateway_ip": info.gateway_ip,
            "netmask": info.netmask,
            "scanned_cidr": info.scan_cidr,
            "note": info.note,
        },
        "discovered": discovered,
        "count": len(discovered),
    })
