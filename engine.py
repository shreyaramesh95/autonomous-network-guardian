"""
engine.py: Enterprise Root Cause Analysis (RCA) & Alarm Correlation Engine for ANG.
Correlates multi-layer network symptoms across the topology DAG to isolate root causes,
suppress redundant cascade alarms, assess blast radius, and recommend autonomous remediation.
"""

from typing import Dict, List, Set, Any, Optional
from topology import DependencyGraph

class DiagnosticEngine:
    def __init__(self, topology: DependencyGraph):
        self.topology = topology

    def diagnose(self, probe_results: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze multi-layer probe telemetry across the dependency DAG.
        Returns correlated incidents, suppressed alarm storm count, blast radius,
        network health index, and actionable remediation runbooks.
        """
        all_nodes = [node["id"] for node in self.topology.get_all_nodes()]
        
        unreachable_nodes = set()
        degraded_nodes = set()
        healthy_nodes = set()

        for nid in all_nodes:
            res = probe_results.get(nid, {"reachable": True, "status": "HEALTHY"})
            if not res.get("reachable", False) or res.get("status") == "UNAVAILABLE":
                unreachable_nodes.add(nid)
            elif res.get("status") == "DEGRADED" or res.get("packet_loss_pct", 0) > 10 or (res.get("latency_ms") and res.get("latency_ms") > 120):
                degraded_nodes.add(nid)
            else:
                healthy_nodes.add(nid)

        # -------------------------------------------------------------
        # STEP 1: Topological Root Cause Analysis
        # A node U is a primary ROOT CAUSE if U is failing, BUT all of U's
        # direct prerequisites (ancestors) are either healthy or non-existent.
        # -------------------------------------------------------------
        root_causes = []
        suppressed_symptoms = []

        for nid in unreachable_nodes:
            prerequisites = self.topology.get_direct_prerequisites(nid)
            failed_parents = [p for p in prerequisites if p in unreachable_nodes]

            if not failed_parents:
                # Primary Root Cause Isolated
                node_meta = self.topology.get_node_info(nid) or {"name": nid, "type": "device"}
                blast_radius = self.topology.get_downstream_blast_radius(nid)
                affected_in_network = [
                    self.topology.get_node_info(desc) for desc in blast_radius if desc in all_nodes
                ]

                severity = self._compute_severity(nid, node_meta)
                actions = self._generate_remediation_actions(nid, node_meta)

                root_causes.append({
                    "node_id": nid,
                    "name": node_meta.get("name", nid),
                    "type": node_meta.get("type", "unknown"),
                    "ip": node_meta.get("ip", "N/A"),
                    "severity": severity,
                    "blast_radius_ids": list(blast_radius),
                    "blast_radius_nodes": affected_in_network,
                    "affected_count": len(blast_radius),
                    "diagnosis": self._generate_diagnosis_text(nid, node_meta),
                    "recommendation": self._generate_recommendations(nid, node_meta),
                    "recommendations": self._generate_recommendations(nid, node_meta),
                    "remediation_actions": actions,
                    "confidence_score": 98.5,
                    "confidence": "HIGH (Deterministically Correlated via DAG)"
                })
            else:
                # Cascading secondary symptom suppressed by ANG
                node_meta = self.topology.get_node_info(nid) or {"name": nid}
                suppressed_symptoms.append({
                    "node_id": nid,
                    "name": node_meta.get("name", nid),
                    "ip": node_meta.get("ip", "N/A"),
                    "type": node_meta.get("type", "unknown"),
                    "caused_by": failed_parents
                })

        # -------------------------------------------------------------
        # STEP 2: Alert Storm Suppression Factor
        # -------------------------------------------------------------
        total_raw_alerts = len(unreachable_nodes)
        num_root_causes = len(root_causes)

        if total_raw_alerts > 0:
            suppression_pct = round((1.0 - (num_root_causes / total_raw_alerts)) * 100, 1)
        else:
            suppression_pct = 0.0

        # -------------------------------------------------------------
        # STEP 3: Quality-of-Service (QoS) Performance Degradations
        # -------------------------------------------------------------
        degradations = []
        for nid in degraded_nodes:
            # Check if upstream node is already down or degraded
            prerequisites = self.topology.get_direct_prerequisites(nid)
            failed_parents = [p for p in prerequisites if p in unreachable_nodes or p in degraded_nodes]
            if not failed_parents:
                node_meta = self.topology.get_node_info(nid) or {"name": nid}
                res = probe_results.get(nid, {})
                degradations.append({
                    "node_id": nid,
                    "name": node_meta.get("name", nid),
                    "latency_ms": res.get("latency_ms", "N/A"),
                    "packet_loss_pct": res.get("packet_loss_pct", 0),
                    "severity": "WARNING",
                    "diagnosis": f"High latency ({res.get('latency_ms')} ms) / Packet Loss ({res.get('packet_loss_pct')}%) detected.",
                    "recommendations": [
                        "Investigate interface bandwidth saturation or bufferbloat.",
                        "Inspect traffic flows for rogue peer-to-peer or bulk transfer activity.",
                        "Verify duplex and speed autonegotiation on the physical port."
                    ]
                })

        # -------------------------------------------------------------
        # STEP 4: Network Health Index (Weighted 0-100%)
        # -------------------------------------------------------------
        health_index = self._calculate_health_index(all_nodes, unreachable_nodes, degraded_nodes)

        return {
            "is_healthy": (len(unreachable_nodes) == 0 and len(degraded_nodes) == 0),
            "health_index": health_index,
            "total_raw_failures": total_raw_alerts,
            "root_causes_count": num_root_causes,
            "suppression_ratio_pct": suppression_pct,
            "root_causes": root_causes,
            "suppressed_symptoms": suppressed_symptoms,
            "degradations": degradations
        }

    def _calculate_health_index(self, all_nodes: List[str], unreachable: Set[str], degraded: Set[str]) -> int:
        """Compute an enterprise weighted network operational health score."""
        if not all_nodes:
            return 100
        
        # Core infrastructure has higher weight
        weights = {
            "NIC_HOST": 15,
            "SW_01": 25,
            "GW_01": 25,
            "ISP_UPLINK": 15,
            "DNS_PRIMARY": 10,
            "DNS_BACKUP": 5,
            "EXT_WEB": 5
        }
        total_weight = 0
        penalized_weight = 0

        for nid in all_nodes:
            w = weights.get(nid, 3) # leaf nodes have weight 3
            total_weight += w
            if nid in unreachable:
                penalized_weight += w
            elif nid in degraded:
                penalized_weight += (w * 0.5)

        score = max(0, min(100, round((1.0 - (penalized_weight / total_weight)) * 100)))
        return score

    def _compute_severity(self, node_id: str, meta: Dict[str, Any]) -> str:
        """Categorize incident severity according to enterprise NOC standards."""
        ntype = meta.get("type", "")
        if node_id in ("GW_01", "SW_01", "ISP_UPLINK") or ntype in ("gateway", "switch", "isp"):
            return "CRITICAL"
        elif node_id in ("DNS_PRIMARY", "DNS_BACKUP", "EXT_WEB") or ntype in ("dns", "cloud"):
            return "MAJOR"
        else:
            return "MINOR"

    def _generate_diagnosis_text(self, node_id: str, meta: Dict[str, Any]) -> str:
        """Map node failure to precise OSI layer root cause diagnosis."""
        node_type = meta.get("type", "")

        if node_id == "NIC_HOST" or node_type == "interface":
            return "Physical Layer 1 / 2 Disconnection: Host Network Interface or cable unplugged."
        elif node_id == "SW_01" or node_type == "switch":
            return "Layer 2 Broadcast Domain Partition: Local Access Switch offline or power loss."
        elif node_id == "GW_01" or node_type == "gateway":
            return "Layer 3 Default Gateway Outage: LAN intra-switch traffic alive, but WAN egress routed traffic dead."
        elif node_id == "ISP_UPLINK" or node_type == "isp":
            return "Layer 3 WAN Transit Blackout: Gateway responsive, but upstream ISP optical carrier lost."
        elif node_id in ("DNS_PRIMARY", "DNS_BACKUP") or node_type == "dns":
            return "Layer 7 Name Resolution Failure: External IP routing functional, but DNS queries timing out."
        elif node_type == "workstation":
            return f"Edge Node Outage: Workstation {meta.get('name', node_id)} unresponsive; no downstream impact."
        else:
            return f"Infrastructure failure on asset {meta.get('name', node_id)}."

    def _generate_recommendations(self, node_id: str, meta: Dict[str, Any]) -> List[str]:
        """Generate prioritized troubleshooting runbooks."""
        node_type = meta.get("type", "")

        if node_id == "NIC_HOST" or node_type == "interface":
            return [
                "Inspect physical RJ-45 copper patch cord on host port.",
                "Verify host Network Interface Card (NIC) driver state.",
                "Ensure local OS interface is not administratively down."
            ]
        elif node_id == "SW_01" or node_type == "switch":
            return [
                "Verify chassis power and redundant PSU state on Lab Switch-01.",
                "Inspect switch management console for Spanning Tree Protocol (STP) topology flaps.",
                "Check uplink optical tranceiver (SFP) light status."
            ]
        elif node_id == "GW_01" or node_type == "gateway":
            return [
                "Verify core router power and thermal indicators.",
                "Check interface GigabitEthernet0/0/0 state and ARP table consistency.",
                "Inspect DHCP server pool allocation to prevent IP address exhaustion.",
                "Do NOT dispatch technicians to individual workstations (cascade impact)."
            ]
        elif node_id == "ISP_UPLINK" or node_type == "isp":
            return [
                "Inspect Optical Network Terminal (ONT) Rx/Tx optical power levels.",
                "Open High-Priority Incident with Internet Service Provider (ISP).",
                "Trigger automated SD-WAN / 4G cellular backup failover."
            ]
        elif node_id in ("DNS_PRIMARY", "DNS_BACKUP") or node_type == "dns":
            return [
                "IP transit verified nominal; issue isolated strictly to Port 53 UDP/TCP.",
                "Reroute default DNS forwarders to secondary resolver (1.1.1.1 / 8.8.8.8).",
                "Flush local DNS caching daemons ('ipconfig /flushdns')."
            ]
        else:
            return [
                "Inspect device physical power cable and wall jack.",
                "Verify static IP vs DHCP reservation to eliminate address collision."
            ]

    def _generate_remediation_actions(self, node_id: str, meta: Dict[str, Any]) -> List[Dict[str, str]]:
        """Actionable self-healing runbook shortcuts for operators."""
        node_type = meta.get("type", "")
        if node_id == "GW_01":
            return [
                {"id": "REBOOT_GW", "label": "⚡ Soft Reboot Gateway (SNMP/SSH)", "icon": "🔄"},
                {"id": "FAILOVER_GW", "label": "🔀 Trigger VRRP/HSRP Secondary Gateway Failover", "icon": "🛡️"}
            ]
        elif node_id in ("DNS_PRIMARY", "DNS_BACKUP"):
            return [
                {"id": "REROUTE_DNS", "label": "🌐 Switch Active Resolver to Cloudflare (1.1.1.1)", "icon": "🔄"},
                {"id": "FLUSH_CACHE", "label": "🧹 Flush Subnet DNS Cache", "icon": "⚡"}
            ]
        elif node_id == "ISP_UPLINK":
            return [
                {"id": "ACTIVATE_CELLULAR", "label": "📡 Engage SD-WAN Backup Cellular Uplink", "icon": "📶"},
                {"id": "PING_ISP_NOC", "label": "📞 Dispatch Automated Webhook to ISP NOC", "icon": "📢"}
            ]
        elif node_id == "SW_01":
            return [
                {"id": "CYCLE_POE", "label": "🔌 Power Cycle Switch via PDU", "icon": "⚡"},
                {"id": "CHECK_STP", "label": "🔍 Audit Spanning Tree Root Bridge", "icon": "📊"}
            ]
        else:
            return [
                {"id": "PING_DEVICE", "label": "🔄 Send Rapid ICMP Burst", "icon": "📡"},
                {"id": "ISOLATE_PORT", "label": "🔒 Isolate Port on Access Switch", "icon": "🛑"}
            ]
