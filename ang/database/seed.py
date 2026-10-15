"""Seed the topology from the PRD example (section 5 / 38) and the mockup.

    PC-01, PC-02, PC-03  -> depend on RTR-01 (their only route out)
    RTR-01               -> the gateway (no dependency)
    SRV-01               -> service host behind the gateway
    PRN-01               -> peripheral behind the gateway
"""
from __future__ import annotations

import sqlite3

# name, ip, type, role, depends_on-name
SEED_DEVICES = [
    ("RTR-01", "192.168.1.1", "Router", "Gateway", None),
    ("PC-01", "192.168.1.10", "Computer", "Client", "RTR-01"),
    ("PC-02", "192.168.1.11", "Computer", "Client", "RTR-01"),
    ("PC-03", "192.168.1.12", "Computer", "Client", "RTR-01"),
    ("SRV-01", "192.168.1.20", "Server", "Service", "RTR-01"),
    ("PRN-01", "192.168.1.30", "Printer", "Peripheral", "RTR-01"),
]


def seed_devices(conn: sqlite3.Connection) -> None:
    """Ensure the seed devices exist. Safe to call repeatedly and concurrently:
    it never touches a name that is already present, so a user's own devices
    and edits are preserved."""
    names = {r["name"] for r in conn.execute("SELECT name FROM devices")}
    if all(d[0] in names for d in SEED_DEVICES):
        return

    for name, ip, dtype, role, _dep in SEED_DEVICES:
        conn.execute(
            "INSERT OR IGNORE INTO devices (name, ip_address, device_type, role, status) "
            "VALUES (?, ?, ?, ?, 'unknown')",
            (name, ip, dtype, role),
        )

    ids = {r["name"]: r["id"] for r in conn.execute("SELECT id, name FROM devices")}
    for name, _ip, _dtype, _role, dep in SEED_DEVICES:
        if dep and name in ids and dep in ids:
            conn.execute(
                "UPDATE devices SET depends_on = ? WHERE id = ? AND depends_on IS NULL",
                (ids[dep], ids[name]),
            )
