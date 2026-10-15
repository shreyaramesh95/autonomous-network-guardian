"""Phase 0 - project skeleton, schema, seed, liveness."""
from __future__ import annotations

EXPECTED_TABLES = {
    "devices", "measurements", "service_checks",
    "incidents", "incident_devices", "diagnostic_events",
}


def test_schema_has_all_tables(conn):
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    names = {r["name"] for r in rows}
    assert EXPECTED_TABLES <= names


def test_devices_table_has_depends_on_column(conn):
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(devices)")}
    assert "depends_on" in cols


def test_seed_creates_six_devices_with_gateway_dependency(conn):
    devices = {d["name"]: d for d in conn.execute("SELECT * FROM devices")}
    assert set(devices) == {"RTR-01", "PC-01", "PC-02", "PC-03", "SRV-01", "PRN-01"}

    gateway = devices["RTR-01"]
    assert gateway["role"] == "Gateway"
    assert gateway["depends_on"] is None

    for client in ("PC-01", "PC-02", "PC-03", "SRV-01", "PRN-01"):
        assert devices[client]["depends_on"] == gateway["id"], client


def test_seed_is_idempotent(db_path):
    from ang.database.db import connection, init_db

    init_db(db_path, seed=True)  # second time
    with connection(db_path) as c:
        n = c.execute("SELECT COUNT(*) AS n FROM devices").fetchone()["n"]
    assert n == 6


def test_index_and_liveness_endpoints(client):
    root = client.get("/")
    assert root.status_code == 302
    assert root.headers["Location"].endswith("/dashboard")
    assert client.get("/api").status_code == 200

    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.get_json()
    assert body["status"] == "ok"
    assert body["devices"]["total"] == 6


def test_devices_endpoint_lists_seed(client):
    r = client.get("/api/devices")
    assert r.status_code == 200
    body = r.get_json()
    assert body["total"] == 6
    names = {d["name"] for d in body["devices"]}
    assert "RTR-01" in names
