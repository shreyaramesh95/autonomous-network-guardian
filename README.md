# Autonomous Network Guardian (ANG)

A rule-based autonomous network monitoring and **root-cause diagnosis** platform
for small networks (labs, classrooms, offices).

Traditional monitors report *symptoms* — "PC1 offline, PC2 offline, internet
down". ANG correlates those symptoms against shared network dependencies and
reports one **probable root cause** with evidence, confidence, priority,
affected devices, a recommended action, and an incident timeline through
recovery.

## Quick start

```bat
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python app.py
```

Open <http://127.0.0.1:5000>. The app auto-creates `database.sqlite` and seeds
the example topology (RTR-01 gateway + PC-01/02/03, SRV-01, PRN-01).

Run **one** server instance at a time. To restart, stop the old process first;
`flask --app app init-db` recreates the database from scratch.

Run the tests:

```bat
set ANG_TESTING=1
.venv\Scripts\python -m pytest
```

## Demo script (PRD success criteria A-F)

Go to **Simulation** and click through the scenarios, watching **Dashboard**:

| Scenario | ANG should show |
|---|---|
| Healthy network | Health ~100, no incidents |
| Individual device failure | Root cause **Individual device failure — PC-02**, *not* gateway; priority Medium |
| Gateway failure | Root cause **Gateway failure**, affected PC-01/02/03, priority Critical, health ~38 |
| DNS failure | **DNS failure**, distinguished from internet failure |
| Internet / WAN failure | **Internet / WAN failure**, distinguished from a gateway fault |
| Recovery | Incident auto-closes after 2 clean cycles; duration recorded; health restored |

"Reset demo data" on the Simulation page clears history for a fresh run.

## Monitoring your real Wi-Fi/network

The sample topology (RTR-01, PC-01/02/03, ...) is fake data for the demo above.
To monitor real devices instead:

1. Open **Devices**, remove the sample devices you don't need (&times; on each row).
2. Click **Scan my Wi-Fi network** - it ping-sweeps your local subnet (the /24
   around your router by default; pass `?cidr=` to scan a different range) and
   lists the real hosts that answered, with the router auto-flagged. This
   needs 2-3 other devices actually connected to the **same Wi-Fi/LAN** so
   they show up - phones, laptops, etc. all work as long as they respond to
   ping (some phones sleep their Wi-Fi radio and won't answer until woken up).
3. Click **Add** next to each device you want monitored (the router first, so
   client devices can be linked to it as their shared dependency).
4. Switch **Live network (real devices)** mode at the top of the Devices page.
   The monitoring cycle now runs real ICMP ping / socket checks against those
   IPs instead of reading simulated scenarios.
5. Watch **Dashboard** - health score, latency and packet loss are now real
   measurements. Unplugging/disconnecting a device, or turning off Wi-Fi on
   your router, produces a real incident through the same diagnosis engine
   used by the simulation.

Notes/limits of live mode (see `ang/monitoring/live_probes.py`):
- Device reachability is plain ICMP ping, shelled out to the OS `ping`
  command - firewalls that block ICMP will show a device as unreachable even
  if it's really up.
- DNS/internet checks always test public endpoints (`example.com`, `1.1.1.1`)
  regardless of mode.
- Switch back to **Simulation** mode at any time without losing registered
  devices.

## Architecture

```
Browser (templates + static/js/app.js, polls every cycle)
        |  HTTP / JSON
        v
Flask  (ang/routes/*  — REST API + page shells)
        |
        v
MonitoringEngine --> DiagnosisEngine --> IncidentManager + health score
  every CYCLE_SECONDS   compares 6 rules    open / maintain / auto-close
        |               picks 1 root cause
        v
ProbeProvider  -- simulation (deterministic scenarios)  -- or --  live (ICMP/socket)
        |
        v
SQLite  (devices, measurements, service_checks, incidents,
         incident_devices, diagnostic_events)
```

The **probe seam** (`ang/monitoring/probes.py`) is the key design point: the
monitoring engine never touches the network directly, so simulation and live
mode are interchangeable and the diagnosis engine is fully unit-testable.

Module layout follows PRD section 28:
`ang/{routes,monitoring,diagnosis,incidents,simulation,database}`.

## REST API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/dashboard` | everything the dashboard needs, one call |
| GET | `/api/health` | network health score (0-100) + summary |
| GET / POST | `/api/devices` | list / register a device |
| GET | `/api/devices/<id>` , `/api/devices/options` | one device / dialog options |
| GET | `/api/diagnosis` | current probable root cause + evidence + hypotheses |
| GET | `/api/incidents` , `/api/incidents/<id>` | incident list / detail + timeline |
| GET | `/api/events` | recent diagnostic events |
| GET | `/api/monitoring` | cycle status, provider, health |
| POST | `/api/monitoring/cycle` | run one cycle now |
| POST | `/api/monitoring/mode` | `{"mode": "simulation" | "live"}` |
| POST | `/api/monitoring/reset-data` | clear history, keep devices |
| GET | `/api/simulation` | scenario list + active |
| POST | `/api/simulation/<action>` | `device-failure`, `gateway-failure`, `dns-failure`, `internet-failure`, `high-latency`, `packet-loss`, `recovery`, `reset` |

## Configuration

All thresholds/weights/intervals are in `ang/config.py`, overridable by
environment variable:

| Var | Default | Meaning |
|---|---|---|
| `ANG_CYCLE_SECONDS` | 10 | monitoring interval |
| `ANG_PROBE_MODE` | `simulation` | `simulation` or `live` |
| `ANG_INITIAL_SCENARIO` | `healthy` | scenario at startup |
| `ANG_INCIDENT_SCORE_THRESHOLD` | 45 | min hypothesis score to be a fault |
| `ANG_RECOVERY_CONFIRM_CYCLES` | 2 | clean cycles to auto-close |
| `ANG_FAILURE_CONFIRM_CYCLES` | 1 | bad cycles before opening (anti-flap) |
| `ANG_DATABASE` | `./database.sqlite` | SQLite path |
| `ANG_LATENCY_{GOOD,MODERATE,HIGH}_MS` | 50 / 100 / 200 | latency bands |
| `ANG_PACKET_LOSS_THRESHOLD_PCT` | 15 | loss band |

## Status

Phases 0-7 complete (scaffolding, monitoring, simulation, diagnosis, incidents +
health, REST API, frontend, demo hardening). 74 tests passing. See
`PROGRESS.md`.
