"""REST API blueprints (PRD 26).

The surface is intentionally partial through Phase 3: devices, monitoring
status, current diagnosis and simulation control. Incident endpoints and the
0-100 network health score arrive in Phase 4.
"""
from __future__ import annotations

from flask import Flask, current_app


def current_engine():
    return current_app.extensions["ang_engine"]


def current_registry():
    return current_app.extensions["ang_registry"]


def register_routes(app: Flask) -> None:
    from .dashboard import bp as dashboard_bp
    from .devices import bp as devices_bp
    from .incidents import bp as incidents_bp
    from .monitoring import bp as monitoring_bp
    from .pages import bp as pages_bp
    from .simulation import bp as simulation_bp

    app.register_blueprint(devices_bp)
    app.register_blueprint(monitoring_bp)
    app.register_blueprint(simulation_bp)
    app.register_blueprint(incidents_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(pages_bp)
