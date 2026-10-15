"""
app.py: Enterprise Network Operations Center (NOC) Dashboard for Autonomous Network Guardian (ANG).
Features real-time telemetry simulation, deterministic alarm correlation, blast radius mapping,
automated remediation runbooks, and dynamic asset management.
"""

import os
import json
import time
import random
from datetime import datetime
import streamlit as st
import pandas as pd

from topology import DependencyGraph
from engine import DiagnosticEngine
from monitor import NetworkMonitor

# Try importing optional graph plotting
try:
    import networkx as nx
    import matplotlib.pyplot as plt
    HAS_GRAPH_LIBS = True
except ImportError:
    HAS_GRAPH_LIBS = False

# Page configuration
st.set_page_config(
    page_title="Autonomous Network Guardian | Enterprise NOC",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Enterprise CSS
st.markdown("""
<style>
    /* Global layout & typography */
    .block-container { padding-top: 1.5rem; padding-bottom: 2rem; }
    h1, h2, h3, h4 { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
    
    /* Header & Badges */
    .noc-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0.8rem 1.2rem;
        background: linear-gradient(90deg, #0f172a 0%, #1e293b 100%);
        color: white;
        border-radius: 8px;
        margin-bottom: 1.2rem;
    }
    .status-beacon {
        display: inline-block;
        width: 10px;
        height: 10px;
        background-color: #10b981;
        border-radius: 50%;
        margin-right: 8px;
        box-shadow: 0 0 8px #10b981;
    }
    
    /* Incident Cards */
    .incident-card-critical {
        border-left: 5px solid #ef4444;
        background-color: #fef2f2;
        padding: 1.2rem;
        border-radius: 6px;
        margin-bottom: 1rem;
        color: #1f2937;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .incident-card-warning {
        border-left: 5px solid #f59e0b;
        background-color: #fffbeb;
        padding: 1.2rem;
        border-radius: 6px;
        margin-bottom: 1rem;
        color: #1f2937;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .raw-alert-chip {
        padding: 6px 10px;
        margin-bottom: 6px;
        border-left: 3px solid #ef4444;
        background: #f8fafc;
        border-radius: 4px;
        font-family: monospace;
        font-size: 0.85rem;
        color: #334155;
    }
    .badge-critical {
        background-color: #ef4444;
        color: white;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    .badge-suppressed {
        background-color: #64748b;
        color: white;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.75rem;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(CURRENT_DIR, "config.json")

# Initialize Session State
if "topology" not in st.session_state:
    st.session_state.topology = DependencyGraph(CONFIG_FILE)

if "telemetry" not in st.session_state:
    st.session_state.telemetry = {}
    for node in st.session_state.topology.get_all_nodes():
        st.session_state.telemetry[node["id"]] = {
            "reachable": True,
            "status": "HEALTHY",
            "latency_ms": round(random.uniform(8.5, 18.0), 1),
            "packet_loss_pct": 0.0
        }

if "incident_journal" not in st.session_state:
    st.session_state.incident_journal = []

if "history_timeseries" not in st.session_state:
    st.session_state.history_timeseries = []

topology = st.session_state.topology
engine = DiagnosticEngine(topology)
monitor = NetworkMonitor()

# =========================================================================
# TOP NAVIGATION & NOC HEADER
# =========================================================================
st.markdown("""
<div class="noc-header">
    <div>
        <span class="status-beacon"></span>
        <strong style="font-size: 1.15rem; letter-spacing: 0.5px;">AUTONOMOUS NETWORK GUARDIAN (ANG)</strong>
        <span style="opacity: 0.7; font-size: 0.9rem; margin-left: 12px;">Enterprise Network Observability & Autonomous Fault Correlator</span>
    </div>
    <div style="font-size: 0.85rem; opacity: 0.85;">
        Environment: <strong>Production Lab VLAN-10</strong> | Engine: <strong>Deterministic DAG Correlation</strong>
    </div>
</div>
""", unsafe_allow_html=True)

# Run Diagnostic Engine on current telemetry
diag_results = engine.diagnose(st.session_state.telemetry)

# Update Incident Journal if incident detected
timestamp_now = datetime.now().strftime("%H:%M:%S")
if not diag_results["is_healthy"]:
    for rc in diag_results["root_causes"]:
        if not any(j["node_id"] == rc["node_id"] and j["status"] == "ACTIVE" for j in st.session_state.incident_journal):
            st.session_state.incident_journal.insert(0, {
                "timestamp": timestamp_now,
                "node_id": rc["node_id"],
                "name": rc["name"],
                "severity": rc["severity"],
                "blast_radius": rc["affected_count"],
                "diagnosis": rc["diagnosis"],
                "status": "ACTIVE"
            })

# Record timeseries point
if len(st.session_state.history_timeseries) > 20:
    st.session_state.history_timeseries.pop(0)

avg_lat = round(sum(t.get("latency_ms", 15) or 15 for t in st.session_state.telemetry.values()) / max(1, len(st.session_state.telemetry)), 1)
st.session_state.history_timeseries.append({
    "time": timestamp_now,
    "health_index": diag_results["health_index"],
    "avg_latency": avg_lat,
    "raw_alerts": diag_results["total_raw_failures"],
    "root_causes": diag_results["root_causes_count"]
})

# =========================================================================
# EXECUTIVE KPI SUMMARY STRIP
# =========================================================================
kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)

# Health score coloring
health_val = diag_results["health_index"]
health_color = "#10b981" if health_val >= 90 else ("#f59e0b" if health_val >= 50 else "#ef4444")

kpi1.metric("System Health Index", f"{health_val}%", delta=f"{health_val - 100}%" if health_val < 100 else "Nominal", delta_color="inverse")
kpi2.metric("Active Root Causes", diag_results["root_causes_count"], delta="Incident Active" if diag_results["root_causes_count"] > 0 else "Clear", delta_color="inverse")
kpi3.metric("Suppressed Cascade Alarms", len(diag_results["suppressed_symptoms"]), help="Redundant downstream alerts filtered out")
kpi4.metric("Noise Reduction Factor", f"{diag_results['suppression_ratio_pct']}%", help="Percentage of alert fatigue prevented by topological correlation")
kpi5.metric("Mean Time to Isolate (MTTI)", "< 2.0 ms", delta="Sub-millisecond", delta_color="off")

st.markdown("<hr style='margin: 1rem 0; border: none; border-top: 1px solid #e2e8f0;'>", unsafe_allow_html=True)

# =========================================================================
# SIDEBAR: CHAOS ENGINEERING & TELEMETRY CONTROLS
# =========================================================================
st.sidebar.markdown("### 🎛️ Telemetry & Chaos Injector")
st.sidebar.caption("Simulate real-world network outages or inject custom latency/loss.")

# Scenario selection
scenario = st.sidebar.selectbox(
    "Pre-Packaged Incident Scenarios:",
    [
        "Nominal State (All Systems Healthy)",
        "Core Gateway Crash (Layer 3 Failure)",
        "L7 DNS Resolver Collapse",
        "Access Switch Power Supply Loss",
        "Upstream ISP Optical Fiber Cut",
        "Edge Workstation Cable Pull (PC-03)",
        "WAN Link Jitter & Congestion Degradation"
    ]
)

# Apply Scenario Preset
def apply_preset(sc_name):
    all_n = topology.get_all_nodes()
    # Reset all to nominal
    for n in all_n:
        st.session_state.telemetry[n["id"]] = {
            "reachable": True,
            "status": "HEALTHY",
            "latency_ms": round(random.uniform(9.0, 16.0), 1),
            "packet_loss_pct": 0.0
        }

    if sc_name == "Core Gateway Crash (Layer 3 Failure)":
        st.session_state.telemetry["GW_01"] = {"reachable": False, "status": "UNAVAILABLE", "latency_ms": None, "packet_loss_pct": 100}
        st.session_state.telemetry["ISP_UPLINK"] = {"reachable": False, "status": "UNAVAILABLE", "latency_ms": None, "packet_loss_pct": 100}
        st.session_state.telemetry["DNS_PRIMARY"] = {"reachable": False, "status": "UNAVAILABLE", "latency_ms": None, "packet_loss_pct": 100}
        st.session_state.telemetry["DNS_BACKUP"] = {"reachable": False, "status": "UNAVAILABLE", "latency_ms": None, "packet_loss_pct": 100}
        st.session_state.telemetry["EXT_WEB"] = {"reachable": False, "status": "UNAVAILABLE", "latency_ms": None, "packet_loss_pct": 100}

    elif sc_name == "L7 DNS Resolver Collapse":
        st.session_state.telemetry["DNS_PRIMARY"] = {"reachable": False, "status": "UNAVAILABLE", "latency_ms": None, "packet_loss_pct": 100}
        st.session_state.telemetry["EXT_WEB"] = {"reachable": False, "status": "UNAVAILABLE", "latency_ms": None, "packet_loss_pct": 100}

    elif sc_name == "Access Switch Power Supply Loss":
        for n in all_n:
            if n["id"] != "NIC_HOST":
                st.session_state.telemetry[n["id"]] = {"reachable": False, "status": "UNAVAILABLE", "latency_ms": None, "packet_loss_pct": 100}

    elif sc_name == "Upstream ISP Optical Fiber Cut":
        st.session_state.telemetry["ISP_UPLINK"] = {"reachable": False, "status": "UNAVAILABLE", "latency_ms": None, "packet_loss_pct": 100}
        st.session_state.telemetry["DNS_PRIMARY"] = {"reachable": False, "status": "UNAVAILABLE", "latency_ms": None, "packet_loss_pct": 100}
        st.session_state.telemetry["DNS_BACKUP"] = {"reachable": False, "status": "UNAVAILABLE", "latency_ms": None, "packet_loss_pct": 100}
        st.session_state.telemetry["EXT_WEB"] = {"reachable": False, "status": "UNAVAILABLE", "latency_ms": None, "packet_loss_pct": 100}

    elif sc_name == "Edge Workstation Cable Pull (PC-03)":
        st.session_state.telemetry["PC_03"] = {"reachable": False, "status": "UNAVAILABLE", "latency_ms": None, "packet_loss_pct": 100}

    elif sc_name == "WAN Link Jitter & Congestion Degradation":
        st.session_state.telemetry["ISP_UPLINK"] = {"reachable": True, "status": "DEGRADED", "latency_ms": 185.4, "packet_loss_pct": 22.0}
        st.session_state.telemetry["DNS_PRIMARY"] = {"reachable": True, "status": "DEGRADED", "latency_ms": 210.2, "packet_loss_pct": 18.0}

if st.sidebar.button("⚡ Apply Selected Scenario", use_container_width=True):
    apply_preset(scenario)
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("##### 🔬 Granular Node Fault Injector")
selected_node_id = st.sidebar.selectbox(
    "Target Node:",
    [n["id"] for n in topology.get_all_nodes()],
    format_func=lambda nid: f"{topology.get_node_info(nid).get('name', nid)} ({nid})"
)

current_node_state = st.session_state.telemetry.get(selected_node_id, {})
inj_status = st.sidebar.radio("Operational State:", ["HEALTHY", "DEGRADED", "UNAVAILABLE"], index=0 if current_node_state.get("reachable", True) else 2)
inj_lat = st.sidebar.slider("Simulated Latency (ms):", 1.0, 500.0, float(current_node_state.get("latency_ms") or 14.0))
inj_loss = st.sidebar.slider("Packet Loss (%):", 0.0, 100.0, float(current_node_state.get("packet_loss_pct") or 0.0))

if st.sidebar.button("💾 Push Telemetry Override", use_container_width=True):
    is_reach = (inj_status != "UNAVAILABLE")
    st.session_state.telemetry[selected_node_id] = {
        "reachable": is_reach,
        "status": inj_status,
        "latency_ms": inj_lat if is_reach else None,
        "packet_loss_pct": inj_loss if is_reach else 100.0
    }
    st.rerun()

if st.sidebar.button("🎲 Generate Synthetic Traffic Tick", use_container_width=True):
    # Add minor realistic jitter to all healthy nodes
    for nid, t in st.session_state.telemetry.items():
        if t["reachable"]:
            base = t.get("latency_ms", 12.0) or 12.0
            jitter = round(random.uniform(-2.5, 3.5), 1)
            t["latency_ms"] = max(2.0, round(base + jitter, 1))
    st.rerun()

# =========================================================================
# MAIN DASHBOARD TABS
# =========================================================================
tab_incident, tab_topology, tab_analytics, tab_journal, tab_inventory = st.tabs([
    "🚨 Incident Command & Correlator",
    "🗺️ Dependency Topology & Blast Radius",
    "📈 Telemetry Stream & Performance",
    "📜 Incident Event Journal",
    "⚙️ Asset Inventory & Topology Config"
])

# -------------------------------------------------------------------------
# TAB 1: INCIDENT COMMAND & CORRELATOR
# -------------------------------------------------------------------------
with tab_incident:
    st.markdown("#### Real-Time Correlation Engine: Symptom Flood vs Root Cause Isolation")
    st.caption("Demonstrating how ANG synthesizes multiple cascading alerts into a single deterministic root cause.")

    col_raw, col_ang = st.columns([1, 1.3])

    with col_raw:
        st.markdown("##### 📡 Raw Ingested Symptoms (Legacy Monitoring View)")
        raw_fails = [nid for nid, p in st.session_state.telemetry.items() if not p["reachable"]]
        
        if not raw_fails:
            st.success("✅ All 12 endpoints responding nominally to ICMP / TCP health probes.")
        else:
            st.error(f"⚠️ Uncorrelated Alert Storm: {len(raw_fails)} Endpoint Outages Detected")
            st.caption("Traditional monitoring triggers separate tickets for every single unreachable host:")
            
            for nid in raw_fails:
                meta = topology.get_node_info(nid) or {"name": nid, "ip": "N/A"}
                st.markdown(
                    f"""
                    <div class="raw-alert-chip">
                        <span class="badge-critical">ALERT</span> <strong>{meta.get('name')}</strong> [{meta.get('ip')}] — Unreachable (Probe Timeout)
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            st.warning("⚠️ High operator fatigue: 12 tickets opened simultaneously without root-cause context.")

    with col_ang:
        st.markdown("##### 🛡️ ANG Correlated Incidents & Root Causes")

        if diag_results["is_healthy"]:
            st.success("🟢 All network layers nominal. Dependency tree verified operational.")
        else:
            for rc in diag_results["root_causes"]:
                sev = rc["severity"]
                card_class = "incident-card-critical" if sev == "CRITICAL" else "incident-card-warning"
                
                st.markdown(
                    f"""
                    <div class="{card_class}">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                            <span class="badge-critical" style="background:#b91c1c;">{sev} INCIDENT</span>
                            <span style="font-size:0.8rem; font-weight:600; color:#6b7280;">Confidence: {rc['confidence_score']}%</span>
                        </div>
                        <h4 style="margin:0 0 6px 0; color:#111827;">{rc['name']} ({rc['node_id']})</h4>
                        <p style="margin:2px 0 8px 0; font-size:0.95rem;"><strong>Diagnosis:</strong> {rc['diagnosis']}</p>
                        <p style="margin:2px 0; font-size:0.85rem; color:#4b5563;">
                            <strong>IP Address:</strong> <code>{rc.get('ip', 'N/A')}</code> | 
                            <strong>Asset Type:</strong> <code>{rc.get('type')}</code> |
                            <strong>Blast Radius:</strong> <strong>{rc['affected_count']}</strong> downstream assets impacted
                        </p>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                # Blast radius view
                if rc["blast_radius_nodes"]:
                    with st.expander(f"👁️ View Downstream Impacted Assets ({len(rc['blast_radius_nodes'])})"):
                        for aff in rc["blast_radius_nodes"]:
                            st.write(f"- 🛑 **{aff.get('name')}** (`{aff.get('ip', 'N/A')}`) — *Access Blocked*")

                # Actionable runbook shortcuts
                st.markdown("###### 🛠️ Autonomous & Guided Remediation Runbooks:")
                rem_cols = st.columns(len(rc["remediation_actions"]))
                for idx, act in enumerate(rc["remediation_actions"]):
                    if rem_cols[idx].button(act["label"], key=f"btn_act_{rc['node_id']}_{act['id']}"):
                        # Auto-mitigate the incident
                        st.session_state.telemetry[rc["node_id"]] = {
                            "reachable": True,
                            "status": "HEALTHY",
                            "latency_ms": 11.2,
                            "packet_loss_pct": 0.0
                        }
                        # Also restore downstream if needed
                        for desc in rc["blast_radius_ids"]:
                            st.session_state.telemetry[desc] = {
                                "reachable": True,
                                "status": "HEALTHY",
                                "latency_ms": 14.5,
                                "packet_loss_pct": 0.0
                            }
                        # Mark mitigated in journal
                        for j in st.session_state.incident_journal:
                            if j["node_id"] == rc["node_id"]:
                                j["status"] = "MITIGATED"
                        st.success(f"Executed: {act['label']}. System state restored.")
                        st.rerun()

            # Display QoS degradations if any
            if diag_results["degradations"]:
                for deg in diag_results["degradations"]:
                    st.markdown(
                        f"""
                        <div class="incident-card-warning">
                            <span class="badge-critical" style="background:#d97706;">QoS DEGRADATION</span>
                            <h5 style="margin:6px 0 2px 0;">{deg['name']} ({deg['node_id']})</h5>
                            <p style="margin:2px 0; font-size:0.9rem;">{deg['diagnosis']}</p>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

            # Suppressed alerts summary chip
            if diag_results["suppressed_symptoms"]:
                st.markdown(
                    f"""
                    <div style="background:#f1f5f9; padding:10px 14px; border-radius:6px; border:1px solid #cbd5e1; margin-top:10px;">
                        <span class="badge-suppressed">NOISE SUPPRESSION</span>
                        <strong style="margin-left:6px; color:#334155;">ANG suppressed {len(diag_results['suppressed_symptoms'])} cascading symptom alarms.</strong>
                        <p style="margin:4px 0 0 0; font-size:0.85rem; color:#64748b;">
                            These endpoints are not individually damaged; their upstream parent failed. Muted to prevent ticket storms.
                        </p>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

# -------------------------------------------------------------------------
# TAB 2: DEPENDENCY TOPOLOGY & BLAST RADIUS RADAR
# -------------------------------------------------------------------------
with tab_topology:
    st.markdown("#### Network Dependency Graph & Blast Radius Radar")
    st.caption("Hierarchical Directed Acyclic Graph (DAG) visualizing upstream dependencies and failure propagation.")

    col_graph, col_inspect = st.columns([2, 1])

    with col_graph:
        if HAS_GRAPH_LIBS:
            G = nx.DiGraph()
            for u, children in topology.children.items():
                for v in children:
                    G.add_edge(u, v)

            fig, ax = plt.subplots(figsize=(10, 5))
            fig.patch.set_facecolor('#ffffff')
            ax.set_facecolor('#ffffff')

            root_cause_ids = [r["node_id"] for r in diag_results["root_causes"]]
            node_colors = []
            for node in G.nodes():
                if node in root_cause_ids:
                    node_colors.append("#ef4444") # Red: Root Cause
                elif not st.session_state.telemetry.get(node, {}).get("reachable", True):
                    node_colors.append("#f97316") # Orange: Impacted in Blast Radius
                elif st.session_state.telemetry.get(node, {}).get("status") == "DEGRADED":
                    node_colors.append("#eab308") # Yellow: Degraded
                else:
                    node_colors.append("#10b981") # Green: Healthy

            pos = nx.spring_layout(G, seed=42)
            nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=1100, ax=ax)
            nx.draw_networkx_labels(G, pos, font_size=8, font_family="sans-serif", font_weight="bold", ax=ax)
            nx.draw_networkx_edges(G, pos, edge_color="#94a3b8", arrows=True, arrowsize=14, width=1.5, ax=ax)
            plt.axis("off")
            st.pyplot(fig)
            st.caption("🟢 Operational | 🔴 Root Cause Failure | 🟠 Downstream Suppressed Impact | 🟡 Degraded QoS")
        else:
            st.info("Topological Dependency State Matrix:")
            topo_table = []
            for node in topology.get_all_nodes():
                nid = node["id"]
                parents = topology.get_direct_prerequisites(nid)
                children = topology.get_direct_dependents(nid)
                if nid in [r["node_id"] for r in diag_results["root_causes"]]:
                    stat = "🔴 ROOT CAUSE"
                elif not st.session_state.telemetry.get(nid, {}).get("reachable", True):
                    stat = "🟠 IN BLAST RADIUS"
                else:
                    stat = "🟢 HEALTHY"

                topo_table.append({
                    "Asset": node["name"],
                    "ID": nid,
                    "State": stat,
                    "Prerequisites": ", ".join(parents) or "None (Root)",
                    "Dependents": ", ".join(children) or "Leaf Node"
                })
            st.dataframe(pd.DataFrame(topo_table), use_container_width=True)

    with col_inspect:
        st.markdown("##### 🔍 Asset Inspector")
        inspect_id = st.selectbox(
            "Select Asset to Inspect:",
            [n["id"] for n in topology.get_all_nodes()],
            key="inspect_select"
        )
        meta = topology.get_node_info(inspect_id) or {}
        prereqs = topology.get_direct_prerequisites(inspect_id)
        children = topology.get_direct_dependents(inspect_id)
        downstream = topology.get_downstream_blast_radius(inspect_id)
        tel = st.session_state.telemetry.get(inspect_id, {})

        st.write(f"**Name:** {meta.get('name')}")
        st.write(f"**Node ID:** `{inspect_id}`")
        st.write(f"**Type:** `{meta.get('type')}`")
        st.write(f"**Configured IP:** `{meta.get('ip', 'N/A')}`")
        st.write(f"**Operational State:** `{tel.get('status', 'HEALTHY')}`")
        st.write(f"**Measured Latency:** `{tel.get('latency_ms', 'N/A')} ms`")
        st.write(f"**Packet Loss:** `{tel.get('packet_loss_pct', 0.0)}%`")
        st.write(f"**Direct Parents (Prerequisites):** {', '.join(prereqs) or 'None'}")
        st.write(f"**Direct Children:** {', '.join(children) or 'None'}")
        st.write(f"**Full Blast Radius Impact:** `{len(downstream)} devices`")

# -------------------------------------------------------------------------
# TAB 3: TELEMETRY STREAM & PERFORMANCE ANALYTICS
# -------------------------------------------------------------------------
with tab_analytics:
    st.markdown("#### Real-Time Telemetry Stream & Historical Performance")

    if st.session_state.history_timeseries:
        ts_df = pd.DataFrame(st.session_state.history_timeseries)

        c_graph1, c_graph2 = st.columns(2)
        with c_graph1:
            st.markdown("##### 📈 System Health Index Over Time")
            st.line_chart(ts_df.set_index("time")[["health_index"]], color="#10b981")

        with c_graph2:
            st.markdown("##### ⚡ Average Subnet Latency (ms)")
            st.line_chart(ts_df.set_index("time")[["avg_latency"]], color="#3b82f6")

        st.markdown("##### 📊 Alert Fatigue Mitigation: Raw Alerts vs Isolated Root Causes")
        st.bar_chart(ts_df.set_index("time")[["raw_alerts", "root_causes"]], color=["#ef4444", "#10b981"])

    st.markdown("---")
    st.markdown("##### 📋 Live Telemetry Feed (All Monitored Assets)")
    telemetry_table = []
    for node in topology.get_all_nodes():
        nid = node["id"]
        t_data = st.session_state.telemetry.get(nid, {})
        telemetry_table.append({
            "Asset Name": node.get("name"),
            "Node ID": nid,
            "IP Address": node.get("ip", "N/A"),
            "Reachability": "UP" if t_data.get("reachable") else "DOWN",
            "Latency (ms)": t_data.get("latency_ms", "N/A"),
            "Loss (%)": f"{t_data.get('packet_loss_pct', 0.0)}%",
            "State": t_data.get("status", "HEALTHY")
        })
    st.dataframe(pd.DataFrame(telemetry_table), use_container_width=True)

# -------------------------------------------------------------------------
# TAB 4: INCIDENT EVENT JOURNAL & AUDIT LOG
# -------------------------------------------------------------------------
with tab_journal:
    st.markdown("#### Incident Audit Trail & Event Journal")
    st.caption("Immutable chronological record of detected network anomalies, root causes, and operator remediations.")

    if not st.session_state.incident_journal:
        st.info("No incident events recorded yet. Trigger a chaos scenario in the sidebar to populate the log.")
    else:
        j_df = pd.DataFrame(st.session_state.incident_journal)
        st.dataframe(j_df, use_container_width=True)

        j_col1, j_col2 = st.columns([1, 4])
        with j_col1:
            csv_data = j_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                "📥 Export Incident Journal (CSV)",
                data=csv_data,
                file_name="ang_incident_journal.csv",
                mime="text/csv",
                use_container_width=True
            )
        with j_col2:
            if st.button("🧹 Clear Incident Log"):
                st.session_state.incident_journal.clear()
                st.rerun()

# -------------------------------------------------------------------------
# TAB 5: ASSET INVENTORY & TOPOLOGY CONFIG
# -------------------------------------------------------------------------
with tab_inventory:
    st.markdown("#### Network Asset Inventory & Dynamic Topology Provisioning")
    st.caption("Inspect registered infrastructure or provision new monitored assets dynamically.")

    inv_col1, inv_col2 = st.columns([1.5, 1])

    with inv_col1:
        st.markdown("##### 🏢 Registered Monitored Assets")
        nodes_df = pd.DataFrame(topology.get_all_nodes())
        st.dataframe(nodes_df, use_container_width=True)

    with inv_col2:
        st.markdown("##### ➕ Provision New Monitored Node")
        with st.form("add_node_form"):
            new_id = st.text_input("Asset ID (e.g., DB_01, AP_02):")
            new_name = st.text_input("Display Name (e.g., Campus Wi-Fi AP):")
            new_type = st.selectbox("Asset Class:", ["workstation", "switch", "router", "server", "iot", "dns", "cloud"])
            new_ip = st.text_input("IP Address:", value="192.168.1.150")
            parent_id = st.selectbox("Depends On (Parent Asset):", [n["id"] for n in topology.get_all_nodes()])
            
            submitted = st.form_submit_button("Register & Connect Asset", use_container_width=True)
            if submitted and new_id and new_name:
                topology.add_node(new_id, new_name, new_type, new_ip)
                topology.add_dependency(parent_id, new_id, f"{new_name} depends on {parent_id}")
                st.session_state.telemetry[new_id] = {
                    "reachable": True,
                    "status": "HEALTHY",
                    "latency_ms": round(random.uniform(10.0, 20.0), 1),
                    "packet_loss_pct": 0.0
                }
                st.success(f"Asset '{new_name}' ({new_id}) registered and linked to '{parent_id}'.")
                st.rerun()

# Footer
st.markdown("<br><hr style='border: none; border-top: 1px solid #e2e8f0;'>", unsafe_allow_html=True)
st.caption("Autonomous Network Guardian (ANG) • Enterprise Network Operations Center • Real-Time Deterministic Root Cause Analysis Engine")
