"""Phase 7 - robustness: clean JSON errors, duplicate handling, concurrent DB."""
from __future__ import annotations

import threading

from ang.database.db import connection
from ang.database.seed import seed_devices


def test_api_500_returns_json_not_html(client, app, monkeypatch):
    from ang.routes import dashboard as dash

    def boom(*a, **k):
        raise RuntimeError("simulated failure")

    monkeypatch.setattr(dash, "compute_health", boom)
    app.extensions["ang_engine"].latest_diagnosis = None
    r = client.get("/api/dashboard")
    assert r.status_code == 500
    assert r.is_json
    assert "simulated failure" in r.get_json()["error"]


def test_duplicate_name_is_400_not_500(client):
    r = client.post("/api/devices", json={
        "name": "PC-01", "ip_address": "10.0.0.9",
        "device_type": "Computer", "role": "Client",
    })
    assert r.status_code == 400
    assert "already exists" in " ".join(r.get_json()["errors"])


def test_duplicate_ip_rejected(client):
    r = client.post("/api/devices", json={
        "name": "PC-99", "ip_address": "192.168.1.10",
        "device_type": "Computer", "role": "Client",
    })
    assert r.status_code == 400


def test_unknown_api_route_is_json_404(client):
    r = client.get("/api/does-not-exist")
    assert r.status_code == 404
    assert r.is_json


def test_seed_is_race_safe(db_path):
    """Ten threads seeding at once must still leave exactly the 6 seed devices."""
    errors = []

    def worker():
        try:
            with connection(db_path) as c:
                seed_devices(c)
        except Exception as e:  # noqa
            errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, errors
    with connection(db_path) as c:
        rows = c.execute("SELECT name FROM devices").fetchall()
    assert sorted(r["name"] for r in rows) == \
        ["PC-01", "PC-02", "PC-03", "PRN-01", "RTR-01", "SRV-01"]


def test_seed_preserves_user_devices(db_path):
    with connection(db_path) as c:
        c.execute("INSERT INTO devices (name, ip_address, device_type, role) "
                  "VALUES ('MINE', '10.0.0.1', 'Computer', 'Client')")
    with connection(db_path) as c:
        seed_devices(c)
        n = c.execute("SELECT COUNT(*) AS n FROM devices WHERE name='MINE'").fetchone()["n"]
    assert n == 1
