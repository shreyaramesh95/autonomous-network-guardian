"""Phase 6 - server-rendered page shells (PRD 24)."""
from __future__ import annotations

import pytest

PAGES = ["/dashboard", "/topology", "/devices", "/diagnosis", "/incidents", "/simulation"]


@pytest.mark.parametrize("path", PAGES)
def test_pages_render(client, path):
    r = client.get(path)
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "Autonomous Network" in html
    assert "app.js" in html
    assert "industry.css" in html


def test_root_redirects_to_dashboard(client):
    r = client.get("/")
    assert r.status_code == 302
    assert r.headers["Location"].endswith("/dashboard")


def test_nav_marks_current_page(client):
    html = client.get("/devices").get_data(as_text=True)
    assert 'href="/devices"' in html
    assert 'aria-current="page"' in html


def test_incident_detail_page_renders(client, app):
    app.extensions["ang_registry"].simulator.set_scenario("gateway")
    app.extensions["ang_engine"].run_cycle()
    r = client.get("/incidents/1")
    assert r.status_code == 200
    assert 'data-incident-id="1"' in r.get_data(as_text=True)


def test_static_assets_served(client):
    assert client.get("/static/js/app.js").status_code == 200
    assert client.get("/static/css/app.css").status_code == 200
    assert client.get("/static/css/industry.css").status_code == 200
