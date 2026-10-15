"""Application factory for Autonomous Network Guardian."""
from __future__ import annotations

import os

from flask import Flask, jsonify, redirect, request

from .config import Config, TestConfig
from .database import db as db_module
from .database.db import init_db
from .monitoring.engine import MonitoringEngine
from .monitoring.registry import ProviderRegistry

__version__ = "0.4.0"  # through Phase 4


def create_app(config_object: type | None = None, **overrides) -> Flask:
    app = Flask(__name__, instance_relative_config=False)

    if config_object is None:
        config_object = TestConfig if os.environ.get("ANG_TESTING") == "1" else Config
    app.config.from_object(config_object)
    app.config.update(overrides)

    # --- storage ------------------------------------------------------------
    db_module.register(app)
    if app.config.get("AUTO_INIT_DB", True):
        _ensure_db(app)

    # --- engines ---------------------------------------------------------
    registry = ProviderRegistry(app.config)
    engine = MonitoringEngine(app.config, registry)
    app.extensions["ang_registry"] = registry
    app.extensions["ang_engine"] = engine

    # --- routes ---------------------------------------------------------
    from .routes import register_routes
    register_routes(app)

    @app.errorhandler(Exception)
    def _json_errors(exc):
        from werkzeug.exceptions import HTTPException

        if isinstance(exc, HTTPException):
            if request.path.startswith("/api/"):
                return jsonify({"error": exc.description, "status": exc.code}), exc.code
            return exc
        app.logger.exception("unhandled error on %s", request.path)
        if request.path.startswith("/api/"):
            return jsonify({"error": f"{type(exc).__name__}: {exc}"}), 500
        raise exc

    @app.get("/")
    def index():
        return redirect("/dashboard")

    @app.get("/api")
    def api_index():
        return jsonify({
            "app": "Autonomous Network Guardian",
            "version": __version__,
            "endpoints": sorted(
                str(r) for r in app.url_map.iter_rules() if str(r).startswith("/api")
            ),
        })

    # --- background monitoring ----------------------------------------
    if app.config.get("START_MONITORING"):
        engine.start()

    return app


def _ensure_db(app: Flask) -> None:
    path = app.config["DATABASE"]
    fresh = not os.path.exists(path) or os.path.getsize(path) == 0
    # init_db is idempotent (CREATE TABLE IF NOT EXISTS); seed only when empty.
    init_db(path, seed=True)
    if fresh:
        app.logger.info("Initialised database at %s", path)
