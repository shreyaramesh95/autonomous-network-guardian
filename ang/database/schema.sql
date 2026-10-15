-- Autonomous Network Guardian - SQLite schema (PRD section 27).
-- Extensions beyond the PRD are marked [ext] and explained inline.

PRAGMA foreign_keys = ON;

-- 27.1 Devices ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS devices (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT    NOT NULL UNIQUE,
    ip_address   TEXT    NOT NULL,
    device_type  TEXT    NOT NULL,            -- Computer | Router | Server | Printer
    role         TEXT    NOT NULL,            -- Client | Gateway | Service | Peripheral
    status       TEXT    NOT NULL DEFAULT 'unknown',  -- online | offline | degraded | unknown
    -- [ext] shared-dependency link. This single column is what lets the
    -- diagnosis engine collapse several device symptoms into one root cause.
    depends_on   INTEGER REFERENCES devices(id) ON DELETE SET NULL,
    created_at   TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- 27.2 Measurements --------------------------------------------------------
CREATE TABLE IF NOT EXISTS measurements (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id    INTEGER NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    timestamp    TEXT    NOT NULL DEFAULT (datetime('now')),
    reachable    INTEGER NOT NULL,            -- 0 / 1
    latency      REAL,                        -- ms, NULL when unreachable
    packet_loss  REAL    NOT NULL DEFAULT 0   -- percentage 0-100
);
CREATE INDEX IF NOT EXISTS idx_measurements_device_ts
    ON measurements (device_id, id DESC);

-- [ext] Service checks: DNS and internet/WAN are not devices, so their probe
-- results need their own table (PRD 9 / 10). Gateway health comes from the
-- gateway device's own measurement rows.
CREATE TABLE IF NOT EXISTS service_checks (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp    TEXT    NOT NULL DEFAULT (datetime('now')),
    service      TEXT    NOT NULL,            -- dns | internet
    reachable    INTEGER NOT NULL,            -- 0 / 1
    latency      REAL,
    detail       TEXT    NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_service_checks_service_ts
    ON service_checks (service, id DESC);

-- 27.3 Incidents (Phase 4) ---------------------------------------------
CREATE TABLE IF NOT EXISTS incidents (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    root_cause      TEXT    NOT NULL,
    rule_name       TEXT    NOT NULL DEFAULT '',
    confidence      INTEGER NOT NULL DEFAULT 0,
    priority        TEXT    NOT NULL,           -- Critical | High | Medium | Low
    status          TEXT    NOT NULL DEFAULT 'open',  -- open | resolved
    started_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    resolved_at     TEXT,
    duration        TEXT,
    -- [ext] recovery is confirmed over N consecutive clean cycles (mockup: 2)
    recovery_cycles INTEGER NOT NULL DEFAULT 0,
    health_at_start INTEGER,
    last_seen_at    TEXT
);

-- 27.4 Incident devices --------------------------------------------------
CREATE TABLE IF NOT EXISTS incident_devices (
    incident_id  INTEGER NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    device_id    INTEGER NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    reason       TEXT    NOT NULL DEFAULT '',
    PRIMARY KEY (incident_id, device_id)
);

-- 27.5 Diagnostic events -----------------------------------------------
CREATE TABLE IF NOT EXISTS diagnostic_events (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_id  INTEGER REFERENCES incidents(id) ON DELETE CASCADE,
    rule_name    TEXT    NOT NULL,
    evidence     TEXT    NOT NULL,
    timestamp    TEXT    NOT NULL DEFAULT (datetime('now'))
);
