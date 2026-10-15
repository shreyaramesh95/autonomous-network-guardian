"""SQLite access layer.

Flask requests use a connection cached on ``flask.g``; the background monitoring
thread opens its own short-lived connection through :func:`connection`.
"""
from __future__ import annotations

import contextlib
import os
import sqlite3

import click
from flask import current_app, g

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")


def _connect(path: str) -> sqlite3.Connection:
    # timeout: wait up to 5s for a lock instead of erroring immediately - the
    # background monitoring thread and request handlers use separate connections.
    conn = sqlite3.connect(path, detect_types=sqlite3.PARSE_DECLTYPES, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    try:
        conn.execute("PRAGMA journal_mode = WAL")
    except sqlite3.OperationalError:
        pass
    return conn


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = _connect(current_app.config["DATABASE"])
    return g.db


def close_db(_exc=None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


@contextlib.contextmanager
def connection(path: str):
    """Standalone connection for code running outside a request context."""
    conn = _connect(path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# columns added after the first schema release: table -> {column: definition}
_MIGRATIONS = {
    "incidents": {
        "recovery_cycles": "INTEGER NOT NULL DEFAULT 0",
        "health_at_start": "INTEGER",
        "last_seen_at": "TEXT",
    },
}


def _migrate(conn: sqlite3.Connection) -> None:
    for table, cols in _MIGRATIONS.items():
        existing = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
        for name, ddl in cols.items():
            if name not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


def init_db(path: str, seed: bool = True) -> None:
    """Create the schema (idempotent) and optionally load the PRD seed devices."""
    from .seed import seed_devices

    with open(SCHEMA_PATH, "r", encoding="utf-8") as fh:
        script = fh.read()
    conn = _connect(path)
    try:
        conn.executescript(script)
        _migrate(conn)
        if seed:
            seed_devices(conn)
        conn.commit()
    finally:
        conn.close()


@click.command("init-db")
@click.option("--no-seed", is_flag=True, help="Create tables without seed devices.")
def init_db_command(no_seed: bool) -> None:
    """flask init-db - (re)create the database file."""
    path = current_app.config["DATABASE"]
    init_db(path, seed=not no_seed)
    click.echo(f"Initialised database at {path}" + ("" if no_seed else " with seed devices"))


def register(app) -> None:
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
