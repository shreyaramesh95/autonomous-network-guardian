"""Monitoring engine (PRD 6, 30 steps 3-6).

Runs a monitoring cycle: probe every device, run the DNS and internet checks,
store the measurements, then hand the fresh Observation to the diagnosis engine.
A background thread repeats this on the configured interval, off the request
path (PRD 33).
"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timezone

from ..database import models as m
from ..database.db import connection
from ..diagnosis.engine import Diagnosis, DiagnosisEngine
from ..diagnosis.observation import Observation
from ..incidents.health import compute_health
from ..incidents.manager import IncidentManager
from .dns_monitor import check_dns
from .internet_monitor import check_internet
from .ping_monitor import status_from_probe
from .registry import ProviderRegistry


class MonitoringEngine:
    def __init__(self, config, registry: ProviderRegistry):
        self.config = config
        self.registry = registry
        self.db_path = config["DATABASE"]
        self.diagnosis_engine = DiagnosisEngine(config)
        self.incident_manager = IncidentManager(config)

        self.last_cycle_at: str | None = None
        self.cycle_count = 0
        self.latest_diagnosis: Diagnosis | None = None
        self.latest_observation: Observation | None = None
        self.latest_health = None
        self.latest_incident_sync: dict | None = None

        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._lock = threading.Lock()

    # -- one cycle ------------------------------------------------------------
    def run_cycle(self, conn=None) -> Diagnosis:
        if conn is not None:
            return self._cycle(conn)
        with connection(self.db_path) as own:
            return self._cycle(own)

    def _cycle(self, conn) -> Diagnosis:
        provider = self.registry.current()
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")

        for d in m.list_devices(conn):
            r = provider.probe_device(d["ip_address"])
            m.add_measurement(conn, d["id"], r.reachable, r.latency_ms,
                              r.packet_loss_pct, timestamp=now)
            m.set_device_status(conn, d["id"], status_from_probe(r, self.config))

        dns = check_dns(provider, self.config)
        m.add_service_check(conn, "dns", dns.reachable, dns.latency_ms, dns.detail, timestamp=now)
        inet = check_internet(provider, self.config)
        m.add_service_check(conn, "internet", inet.reachable, inet.latency_ms,
                            inet.detail, timestamp=now)
        conn.commit()

        obs = Observation.from_db(conn)
        obs.timestamp = now
        diagnosis = self.diagnosis_engine.diagnose(obs)
        health = compute_health(obs, self.config)
        sync = self.incident_manager.sync(conn, diagnosis, obs, health, now=now)

        with self._lock:
            self.latest_observation = obs
            self.latest_diagnosis = diagnosis
            self.latest_health = health
            self.latest_incident_sync = sync
            self.last_cycle_at = now
            self.cycle_count += 1
        return diagnosis

    # -- background loop ----------------------------------------------------
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="ang-monitor", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=timeout)

    def _loop(self) -> None:
        interval = max(1, int(self.config["CYCLE_SECONDS"]))
        # first cycle almost immediately so the dashboard is populated
        while not self._stop.is_set():
            try:
                self.run_cycle()
            except Exception as exc:  # never let the loop die
                print(f"[ang-monitor] cycle error: {exc}")
            self._stop.wait(interval)

    # -- snapshot for the API ---------------------------------------------
    def status(self) -> dict:
        with self._lock:
            return {
                "last_cycle_at": self.last_cycle_at,
                "cycle_count": self.cycle_count,
                "cycle_seconds": int(self.config["CYCLE_SECONDS"]),
                "provider": self.registry.describe(),
                "running": bool(self._thread and self._thread.is_alive()),
                "health_score": self.latest_health.score if self.latest_health else None,
                "incident_actions": (self.latest_incident_sync or {}).get("actions", []),
            }
