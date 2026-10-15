"""Central configuration for Autonomous Network Guardian.

Every threshold, weight and interval the PRD calls "configurable" lives here so
the monitoring, diagnosis, incident and health-score code never hard-codes a
magic number. Values can be overridden with environment variables (prefix
``ANG_``) for quick experiments during a demo.
"""
from __future__ import annotations

import os

BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


class Config:
    # --- Flask -----------------------------------------------------------
    SECRET_KEY = os.environ.get("ANG_SECRET_KEY", "ang-dev-secret")
    TESTING = False

    # --- Storage -------------------------------------------------------
    DATABASE = os.environ.get("ANG_DATABASE", os.path.join(BASE_DIR, "database.sqlite"))

    # --- Monitoring cycle --------------------------------------------------
    CYCLE_SECONDS = _int("ANG_CYCLE_SECONDS", 10)      # PRD 6.1 monitoring interval
    PING_COUNT = _int("ANG_PING_COUNT", 5)             # PRD 7.3 packet-loss sample size
    PING_TIMEOUT_MS = _int("ANG_PING_TIMEOUT_MS", 1000)

    # --- Latency classification (ms) -- PRD 7.2 table -------------------
    LATENCY_GOOD_MS = _int("ANG_LATENCY_GOOD_MS", 50)
    LATENCY_MODERATE_MS = _int("ANG_LATENCY_MODERATE_MS", 100)
    LATENCY_HIGH_MS = _int("ANG_LATENCY_HIGH_MS", 200)

    # --- Packet loss ----------------------------------------------------
    PACKET_LOSS_THRESHOLD_PCT = _int("ANG_PACKET_LOSS_THRESHOLD_PCT", 15)

    # --- External connectivity checks -- PRD 9 / 10 --------------------
    INTERNET_TEST_IP = os.environ.get("ANG_INTERNET_TEST_IP", "1.1.1.1")
    INTERNET_TEST_PORT = _int("ANG_INTERNET_TEST_PORT", 53)
    DNS_TEST_HOSTNAME = os.environ.get("ANG_DNS_TEST_HOSTNAME", "example.com")

    # --- Diagnosis engine --------------------------------------------------
    # A fault hypothesis must score at least this much to be treated as a real
    # fault (and, later, to open an incident). Below it the network is "healthy".
    INCIDENT_SCORE_THRESHOLD = _int("ANG_INCIDENT_SCORE_THRESHOLD", 45)
    # How many consecutive clean cycles confirm a recovery (mockup: 2).
    RECOVERY_CONFIRM_CYCLES = _int("ANG_RECOVERY_CONFIRM_CYCLES", 2)
    # How many consecutive failing cycles before a symptom is "real" (anti-flap).
    FAILURE_CONFIRM_CYCLES = _int("ANG_FAILURE_CONFIRM_CYCLES", 1)

    # --- Network health score weights -- PRD 21.1 (sum = 100) -----------
    HEALTH_WEIGHTS = {
        "device_availability": _int("ANG_HW_DEVICE", 25),
        "latency": _int("ANG_HW_LATENCY", 15),
        "packet_loss": _int("ANG_HW_LOSS", 15),
        "gateway": _int("ANG_HW_GATEWAY", 20),
        "dns": _int("ANG_HW_DNS", 10),
        "internet": _int("ANG_HW_INTERNET", 15),
    }

    # --- Probe provider --------------------------------------------------
    # "simulation" (deterministic, safe, the demo path) or "live" (real ICMP /
    # sockets). Simulation is the default so the app is useful with no network.
    PROBE_MODE = os.environ.get("ANG_PROBE_MODE", "simulation")
    INITIAL_SCENARIO = os.environ.get("ANG_INITIAL_SCENARIO", "healthy")

    # Start the background monitoring thread when the app is created.
    START_MONITORING = os.environ.get("ANG_START_MONITORING", "1") == "1"


class TestConfig(Config):
    TESTING = True
    START_MONITORING = False
    CYCLE_SECONDS = 1
