"""
cli_demo.py: Zero-Dependency Interactive Terminal CLI for Autonomous Network Guardian.
Runs on pure standard library Python on any Windows, Linux, or macOS terminal.
Ideal for college lab demonstrations without third-party package installation.
"""

import os
import sys
import time
from topology import DependencyGraph
from engine import DiagnosticEngine
from monitor import NetworkMonitor

def print_banner():
    print("=" * 72)
    print("   AUTONOMOUS NETWORK GUARDIAN (ANG) - NOC INCIDENT COMMAND CONSOLE")
    print("   Enterprise Dependency-Aware Network Fault Diagnosis & Correlation")
    print("=" * 72)

def format_status(status_bool):
    return "[ OK ]" if status_bool else "[FAIL]"

def run_scenario(name, description, override_dict, topology, engine):
    print("\n" + "#" * 72)
    print(f"SCENARIO: {name}")
    print(f"Description: {description}")
    print("#" * 72)

    all_nodes = topology.get_all_nodes()
    probe_results = {}

    for node in all_nodes:
        nid = node["id"]
        is_up = override_dict.get(nid, True)
        probe_results[nid] = {
            "reachable": is_up,
            "status": "HEALTHY" if is_up else "UNAVAILABLE",
            "latency_ms": 14.2 if is_up else None
        }

    # 1. Simulate Traditional Ping Monitor Output
    print("\n--- 1. TRADITIONAL MONITORING ALERT OUTPUT (Uncorrelated Ping Sweep) ---")
    raw_failures = [nid for nid, p in probe_results.items() if not p["reachable"]]
    if not raw_failures:
        print("  All 12 endpoints responding normally. 0 alerts raised.")
    else:
        print(f"  [ALERT STORM] {len(raw_failures)} separate critical alerts triggered!")
        for nid in raw_failures:
            node_meta = topology.get_node_info(nid)
            print(f"    [CRITICAL ALERT] Device '{node_meta['name']}' ({nid}) unreachable!")
        print("  --> Result: Administrator faces alert fatigue and must inspect all devices.")

    # 2. Run ANG Diagnostic Engine
    print("\n--- 2. AUTONOMOUS NETWORK GUARDIAN (ANG) OUTPUT ---")
    analysis = engine.diagnose(probe_results)

    if analysis["is_healthy"]:
        print("  [STATUS: HEALTHY] No root-cause incidents detected in dependency tree.")
    else:
        print(f"  Raw Symptoms Detected : {analysis['total_raw_failures']}")
        print(f"  Root Causes Isolated  : {analysis['root_causes_count']}")
        print(f"  Suppression Ratio     : {analysis['suppression_ratio_pct']}% noise reduction\n")

        for idx, rc in enumerate(analysis["root_causes"], 1):
            print(f"  ================ ROOT CAUSE #{idx} ================")
            print(f"  Suspect Device  : {rc['name']} (ID: {rc['node_id']})")
            print(f"  Diagnosis       : {rc['diagnosis']}")
            print(f"  Diagnostic Conf : {rc['confidence']}")
            print(f"  Blast Radius    : {rc['affected_count']} dependent nodes affected:")
            for aff in rc["blast_radius_nodes"]:
                print(f"     * {aff['name']} ({aff['id']})")
            print("\n  Recommended Recovery Actions:")
            for step in rc["recommendation"]:
                print(f"     -> {step}")
            print("  " + "=" * 50)

        if analysis["suppressed_symptoms"]:
            print(f"\n  [ANG SUPPRESSION] Suppressed {len(analysis['suppressed_symptoms'])} downstream alerts")
            print("  (These devices are not broken; their upstream prerequisite failed).")

def interactive_menu():
    config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    topology = DependencyGraph(config_file)
    engine = DiagnosticEngine(topology)
    monitor = NetworkMonitor()

    while True:
        print_banner()
        print("Select an option to test:")
        print("1. Scenario 1: Default Gateway Down (Demonstrates Alert Suppression)")
        print("2. Scenario 2: DNS Resolution Failure (Internet IP alive, domain dead)")
        print("3. Scenario 3: Local Access Switch Failure (Lab isolated)")
        print("4. Scenario 4: ISP Optical Fiber Cut")
        print("5. Scenario 5: Single Workstation Unplugged (PC-03)")
        print("6. Scenario 6: All Systems Fully Healthy")
        print("7. Live Probing of Current Host")
        print("0. Exit")
        print("-" * 72)

        choice = input("Enter choice (0-7): ").strip()

        if choice == "1":
            run_scenario(
                "Default Gateway Router Failure",
                "Gateway (192.168.1.1) fails. Downstream ISP, DNS and Web also report unreachable.",
                {
                    "GW_01": False,
                    "ISP_UPLINK": False,
                    "DNS_PRIMARY": False,
                    "DNS_BACKUP": False,
                    "EXT_WEB": False
                },
                topology, engine
            )
        elif choice == "2":
            run_scenario(
                "DNS Resolution Outage",
                "Public routing is functional, but Primary DNS server fails to resolve queries.",
                {
                    "DNS_PRIMARY": False,
                    "EXT_WEB": False
                },
                topology, engine
            )
        elif choice == "3":
            run_scenario(
                "Access Switch Failure",
                "Switch-01 powers off. All connected workstations and the gateway become unreachable from host.",
                {
                    "SW_01": False,
                    "PC_01": False,
                    "PC_02": False,
                    "PC_03": False,
                    "PC_04": False,
                    "PC_05": False,
                    "GW_01": False,
                    "ISP_UPLINK": False,
                    "DNS_PRIMARY": False,
                    "DNS_BACKUP": False,
                    "EXT_WEB": False
                },
                topology, engine
            )
        elif choice == "4":
            run_scenario(
                "ISP Fiber Optical Cut",
                "Local LAN and Gateway are functional, but ISP WAN uplink is dead.",
                {
                    "ISP_UPLINK": False,
                    "DNS_PRIMARY": False,
                    "DNS_BACKUP": False,
                    "EXT_WEB": False
                },
                topology, engine
            )
        elif choice == "5":
            run_scenario(
                "Isolated Workstation Cable Disconnect",
                "Only PC-03 loses connection; infrastructure remains 100% healthy.",
                {
                    "PC_03": False
                },
                topology, engine
            )
        elif choice == "6":
            run_scenario(
                "Baseline Healthy State",
                "All devices and network services nominal.",
                {},
                topology, engine
            )
        elif choice == "7":
            print("\nProbing live host interfaces, gateway and internet...")
            probes = monitor.probe_live_system()
            run_scenario("Live System Probe", "Real-time probe results from this machine", {
                k: v["reachable"] for k, v in probes.items()
            }, topology, engine)
        elif choice == "0":
            print("\nExiting Autonomous Network Guardian. Good luck with your project defense!\n")
            sys.exit(0)
        else:
            print("\nInvalid choice. Please enter a number from 0 to 7.")

        input("\n[Press Enter to return to main menu...]")

if __name__ == "__main__":
    interactive_menu()
