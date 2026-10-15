# Autonomous Network Guardian (ANG)
### Enterprise Dependency-Aware Network Observability & Fault Correlation Platform

---

## 📌 Platform Overview
**Autonomous Network Guardian (ANG)** is an enterprise Network Operations Center (NOC) observability platform. When core network infrastructure (switches, routers, or ISP uplinks) suffers an outage, conventional monitoring systems emit an uncoordinated storm of hundreds of downstream alarms.

ANG models the network infrastructure as a **Directed Acyclic Graph (DAG)** and employs a deterministic correlation engine to:
1. **Isolate Root Causes:** Trace multi-layer symptoms (ICMP, TCP, DNS) to the true origin of failure in $<2\text{ ms}$.
2. **Suppress Cascade Alarms:** Eliminate up to 95% of alert noise by grouping downstream symptoms under the root cause.
3. **Map Blast Radius:** Instantly identify all dependent end-users, services, and workloads impacted.
4. **Trigger Autonomous Runbooks:** Provide one-click self-healing remediation actions (e.g. gateway reboot, DNS failover, SD-WAN uplink switch).

---

## 🚀 Quickstart Guide (VS Code / Terminal)

### 1. Install Dependencies
```powershell
pip install -r requirements.txt
```

### 2. Launch the NOC Web Dashboard
```powershell
streamlit run app.py
```
Or press **F5** in VS Code to launch with the included [`.vscode/launch.json`](.vscode/launch.json).

### 3. Alternative: Zero-Dependency Terminal Console
```powershell
python cli_demo.py
```

---

## 🖥️ NOC Dashboard Features

* **Top Executive KPI Bar:** Live System Health Index (weighted 0-100%), Active Root Causes, Suppressed Alarms, Noise Reduction Factor, and MTTI.
* **Chaos Engineering & Telemetry Injector:**
  * Pre-packaged outage scenarios (Gateway Crash, DNS Resolver Collapse, Access Switch Loss, ISP Optical Cut, Jitter Degradation).
  * Granular per-node fault overrides with custom Latency (ms) and Packet Loss (%) sliders.
  * Synthetic traffic generation with realistic jitter variance.
* **Incident Command Center:** Side-by-side comparison of Legacy Monitoring Alert Flood vs. ANG Root Cause Cards with autonomous remediation runbooks.
* **Dependency Graph & Blast Radius Radar:** Interactive DAG topology visualization with deep asset inspection.
* **Real-Time Telemetry & Analytics:** Live latency stream charts, alert fatigue mitigation metrics, and tabular telemetry feeds.
* **Incident Audit Journal:** Chronological event log with CSV export capability.
* **Asset Inventory & Dynamic Provisioning:** Live view of registered infrastructure with a form to provision and link new monitored devices dynamically.

---

## 🗂️ Project Architecture

```
autonomous_network_guardian/
│
├── config.json          # Network topology & dependency declarations
├── topology.py          # Directed Acyclic Graph (DAG) traversal engine
├── engine.py            # Deterministic root cause analysis & correlation engine
├── monitor.py           # Multi-layer active probing module (ICMP, TCP, DNS)
├── app.py               # Enterprise Streamlit NOC Dashboard
├── cli_demo.py          # Interactive terminal CLI console
├── requirements.txt     # Python dependencies
└── .vscode/
    └── launch.json      # One-click F5 launcher for VS Code
```
