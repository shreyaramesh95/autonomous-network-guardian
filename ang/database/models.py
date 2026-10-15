"""Thin data-access helpers over the SQLite tables.

Not an ORM - just the handful of queries the engines and routes need, kept in
one place so SQL does not leak everywhere (PRD 33: maintainability).
"""
from __future__ import annotations

import sqlite3
from typing import Any, Optional

Row = sqlite3.Row


# --- devices -----------------------------------------------------------------
def list_devices(conn: sqlite3.Connection) -> list[Row]:
    return conn.execute(
        "SELECT * FROM devices ORDER BY "
        "CASE role WHEN 'Gateway' THEN 0 WHEN 'Client' THEN 1 "
        "WHEN 'Service' THEN 2 ELSE 3 END, name"
    ).fetchall()


def get_device(conn: sqlite3.Connection, device_id: int) -> Optional[Row]:
    return conn.execute("SELECT * FROM devices WHERE id = ?", (device_id,)).fetchone()


def get_gateway(conn: sqlite3.Connection) -> Optional[Row]:
    return conn.execute(
        "SELECT * FROM devices WHERE role = 'Gateway' ORDER BY id LIMIT 1"
    ).fetchone()


def create_device(
    conn: sqlite3.Connection,
    name: str,
    ip_address: str,
    device_type: str,
    role: str,
    depends_on: Optional[int] = None,
) -> int:
    cur = conn.execute(
        "INSERT INTO devices (name, ip_address, device_type, role, depends_on) "
        "VALUES (?, ?, ?, ?, ?)",
        (name, ip_address, device_type, role, depends_on),
    )
    return int(cur.lastrowid)


def set_device_status(conn: sqlite3.Connection, device_id: int, status: str) -> None:
    conn.execute("UPDATE devices SET status = ? WHERE id = ?", (status, device_id))


def delete_device(conn: sqlite3.Connection, device_id: int) -> None:
    conn.execute("DELETE FROM devices WHERE id = ?", (device_id,))


# --- measurements ----------------------------------------------------------
def add_measurement(
    conn: sqlite3.Connection,
    device_id: int,
    reachable: bool,
    latency: Optional[float],
    packet_loss: float,
    timestamp: Optional[str] = None,
) -> None:
    if timestamp is None:
        conn.execute(
            "INSERT INTO measurements (device_id, reachable, latency, packet_loss) "
            "VALUES (?, ?, ?, ?)",
            (device_id, int(reachable), latency, packet_loss),
        )
    else:
        conn.execute(
            "INSERT INTO measurements (device_id, timestamp, reachable, latency, packet_loss) "
            "VALUES (?, ?, ?, ?, ?)",
            (device_id, timestamp, int(reachable), latency, packet_loss),
        )


def latest_measurements(conn: sqlite3.Connection) -> dict[int, Row]:
    """device_id -> most recent measurement row."""
    rows = conn.execute(
        "SELECT m.* FROM measurements m "
        "JOIN (SELECT device_id, MAX(id) AS mid FROM measurements GROUP BY device_id) x "
        "  ON m.id = x.mid"
    ).fetchall()
    return {r["device_id"]: r for r in rows}


def recent_measurements(
    conn: sqlite3.Connection, device_id: int, limit: int
) -> list[Row]:
    return conn.execute(
        "SELECT * FROM measurements WHERE device_id = ? ORDER BY id DESC LIMIT ?",
        (device_id, limit),
    ).fetchall()


# --- service checks -------------------------------------------------------
def add_service_check(
    conn: sqlite3.Connection,
    service: str,
    reachable: bool,
    latency: Optional[float] = None,
    detail: str = "",
    timestamp: Optional[str] = None,
) -> None:
    if timestamp is None:
        conn.execute(
            "INSERT INTO service_checks (service, reachable, latency, detail) "
            "VALUES (?, ?, ?, ?)",
            (service, int(reachable), latency, detail),
        )
    else:
        conn.execute(
            "INSERT INTO service_checks (service, timestamp, reachable, latency, detail) "
            "VALUES (?, ?, ?, ?, ?)",
            (service, timestamp, int(reachable), latency, detail),
        )


def latest_service_check(conn: sqlite3.Connection, service: str) -> Optional[Row]:
    return conn.execute(
        "SELECT * FROM service_checks WHERE service = ? ORDER BY id DESC LIMIT 1",
        (service,),
    ).fetchone()


def recent_service_checks(
    conn: sqlite3.Connection, service: str, limit: int
) -> list[Row]:
    return conn.execute(
        "SELECT * FROM service_checks WHERE service = ? ORDER BY id DESC LIMIT ?",
        (service, limit),
    ).fetchall()


def row_to_dict(row: Optional[Row]) -> Optional[dict[str, Any]]:
    return dict(row) if row is not None else None


# --- incidents -----------------------------------------------------------
def open_incidents(conn: sqlite3.Connection) -> list[Row]:
    return conn.execute(
        "SELECT * FROM incidents WHERE status = 'open' ORDER BY id"
    ).fetchall()


def open_incident_for_rule(conn: sqlite3.Connection, rule_name: str) -> Optional[Row]:
    return conn.execute(
        "SELECT * FROM incidents WHERE status = 'open' AND rule_name = ? ORDER BY id DESC LIMIT 1",
        (rule_name,),
    ).fetchone()


def list_incidents(conn: sqlite3.Connection) -> list[Row]:
    return conn.execute("SELECT * FROM incidents ORDER BY id DESC").fetchall()


def get_incident(conn: sqlite3.Connection, incident_id: int) -> Optional[Row]:
    return conn.execute(
        "SELECT * FROM incidents WHERE id = ?", (incident_id,)
    ).fetchone()


def create_incident(
    conn: sqlite3.Connection,
    root_cause: str,
    rule_name: str,
    confidence: int,
    priority: str,
    started_at: str,
    health_at_start: Optional[int],
) -> int:
    cur = conn.execute(
        "INSERT INTO incidents (root_cause, rule_name, confidence, priority, "
        "status, started_at, last_seen_at, health_at_start) "
        "VALUES (?, ?, ?, ?, 'open', ?, ?, ?)",
        (root_cause, rule_name, confidence, priority, started_at, started_at,
         health_at_start),
    )
    return int(cur.lastrowid)


def touch_incident(
    conn: sqlite3.Connection, incident_id: int, confidence: int, priority: str,
    last_seen_at: str,
) -> None:
    conn.execute(
        "UPDATE incidents SET confidence = ?, priority = ?, last_seen_at = ?, "
        "recovery_cycles = 0 WHERE id = ?",
        (confidence, priority, last_seen_at, incident_id),
    )


def bump_recovery(conn: sqlite3.Connection, incident_id: int) -> int:
    conn.execute(
        "UPDATE incidents SET recovery_cycles = recovery_cycles + 1 WHERE id = ?",
        (incident_id,),
    )
    return conn.execute(
        "SELECT recovery_cycles FROM incidents WHERE id = ?", (incident_id,)
    ).fetchone()["recovery_cycles"]


def resolve_incident(
    conn: sqlite3.Connection, incident_id: int, resolved_at: str, duration: str
) -> None:
    conn.execute(
        "UPDATE incidents SET status = 'resolved', resolved_at = ?, duration = ? "
        "WHERE id = ?",
        (resolved_at, duration, incident_id),
    )


def set_incident_devices(
    conn: sqlite3.Connection, incident_id: int, devices: list[tuple[int, str]]
) -> None:
    conn.execute("DELETE FROM incident_devices WHERE incident_id = ?", (incident_id,))
    conn.executemany(
        "INSERT OR REPLACE INTO incident_devices (incident_id, device_id, reason) "
        "VALUES (?, ?, ?)",
        [(incident_id, did, reason) for did, reason in devices],
    )


def incident_devices(conn: sqlite3.Connection, incident_id: int) -> list[Row]:
    return conn.execute(
        "SELECT d.name, d.ip_address, id.reason FROM incident_devices id "
        "JOIN devices d ON d.id = id.device_id WHERE id.incident_id = ? ORDER BY d.name",
        (incident_id,),
    ).fetchall()


def add_diagnostic_event(
    conn: sqlite3.Connection, incident_id: Optional[int], rule_name: str,
    evidence: str, timestamp: Optional[str] = None,
) -> None:
    if timestamp is None:
        conn.execute(
            "INSERT INTO diagnostic_events (incident_id, rule_name, evidence) "
            "VALUES (?, ?, ?)",
            (incident_id, rule_name, evidence),
        )
    else:
        conn.execute(
            "INSERT INTO diagnostic_events (incident_id, rule_name, evidence, timestamp) "
            "VALUES (?, ?, ?, ?)",
            (incident_id, rule_name, evidence, timestamp),
        )


def diagnostic_events(conn: sqlite3.Connection, incident_id: int) -> list[Row]:
    return conn.execute(
        "SELECT * FROM diagnostic_events WHERE incident_id = ? ORDER BY id",
        (incident_id,),
    ).fetchall()


def recent_diagnostic_events(conn: sqlite3.Connection, limit: int) -> list[Row]:
    return conn.execute(
        "SELECT de.*, i.root_cause FROM diagnostic_events de "
        "LEFT JOIN incidents i ON i.id = de.incident_id ORDER BY de.id DESC LIMIT ?",
        (limit,),
    ).fetchall()
