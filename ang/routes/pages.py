"""Server-rendered page shells (PRD 24). Each page's data is filled in by JS
polling the JSON API every monitoring cycle (PRD 30 step 13)."""
from __future__ import annotations

from flask import Blueprint, render_template

bp = Blueprint("pages", __name__)

_NAV = [
    ("dashboard", "Dashboard", "/dashboard"),
    ("topology", "Topology", "/topology"),
    ("devices", "Devices", "/devices"),
    ("diagnosis", "Diagnosis", "/diagnosis"),
    ("incidents", "Incidents", "/incidents"),
    ("simulation", "Simulation", "/simulation"),
]


def _render(page: str, **ctx):
    return render_template(f"{page}.html", page=page, nav=_NAV, **ctx)


@bp.get("/dashboard")
def dashboard():
    return _render("dashboard")


@bp.get("/topology")
def topology():
    return _render("topology")


@bp.get("/devices")
def devices():
    return _render("devices")


@bp.get("/diagnosis")
def diagnosis():
    return _render("diagnosis")


@bp.get("/incidents")
def incidents():
    return _render("incidents")


@bp.get("/incidents/<int:incident_id>")
def incident_detail(incident_id: int):
    return _render("incident_detail", incident_id=incident_id)


@bp.get("/simulation")
def simulation():
    return _render("simulation")
