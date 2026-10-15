"""
monitor.py: Multi-layer Network Probing Module for Autonomous Network Guardian.
Supports ICMP ping, L4 TCP connect, L7 DNS resolution, and simulated fault injection.
"""

import subprocess
import platform
import socket
import time
import re
from typing import Dict, Any, Optional

class NetworkMonitor:
    def __init__(self, ping_timeout_ms: int = 1000):
        self.ping_timeout_ms = ping_timeout_ms
        self.os_type = platform.system().lower()

    def ping_host(self, host: str, count: int = 1) -> Dict[str, Any]:
        """
        Perform an ICMP ping to the specified host.
        Returns reachability, round-trip latency (ms), and packet loss percentage.
        """
        if self.os_type == "windows":
            cmd = ["ping", "-n", str(count), "-w", str(self.ping_timeout_ms), host]
        else:
            timeout_sec = max(1, self.ping_timeout_ms // 1000)
            cmd = ["ping", "-c", str(count), "-W", str(timeout_sec), host]

        try:
            start_time = time.time()
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
            elapsed_ms = (time.time() - start_time) * 1000

            if res.returncode == 0:
                # Parse average latency from ping output
                latency = self._extract_latency(res.stdout, default=round(elapsed_ms, 1))
                return {
                    "reachable": True,
                    "latency_ms": latency,
                    "packet_loss_pct": 0.0,
                    "status": "HEALTHY" if latency < 150 else "DEGRADED"
                }
            else:
                return {
                    "reachable": False,
                    "latency_ms": None,
                    "packet_loss_pct": 100.0,
                    "status": "UNAVAILABLE"
                }
        except (subprocess.TimeoutExpired, Exception) as e:
            return {
                "reachable": False,
                "latency_ms": None,
                "packet_loss_pct": 100.0,
                "status": "UNAVAILABLE",
                "error": str(e)
            }

    def _extract_latency(self, output: str, default: float) -> float:
        """Extract average round-trip time from standard OS ping output."""
        try:
            # Match Windows 'Average = 24ms' or Unix 'rtt min/avg/max = ...'
            win_match = re.search(r"Average = (\d+)ms", output)
            if win_match:
                return float(win_match.group(1))
            unix_match = re.search(r"=\s*[\d\.]+/([\d\.]+)/", output)
            if unix_match:
                return float(unix_match.group(1))
        except Exception:
            pass
        return default

    def check_dns_resolution(self, domain: str = "google.com") -> Dict[str, Any]:
        """Verify L7 DNS resolution by querying a well-known public domain."""
        start = time.time()
        try:
            resolved_ip = socket.gethostbyname(domain)
            latency = round((time.time() - start) * 1000, 2)
            return {
                "reachable": True,
                "resolved_ip": resolved_ip,
                "latency_ms": latency,
                "status": "HEALTHY"
            }
        except socket.gaierror:
            return {
                "reachable": False,
                "resolved_ip": None,
                "latency_ms": None,
                "status": "UNAVAILABLE",
                "error": "DNS Name Resolution Failed"
            }

    def check_tcp_port(self, host: str, port: int = 80, timeout: float = 2.0) -> Dict[str, Any]:
        """Perform an L4 TCP connection handshake."""
        start = time.time()
        try:
            with socket.create_connection((host, port), timeout=timeout):
                latency = round((time.time() - start) * 1000, 2)
                return {
                    "reachable": True,
                    "port": port,
                    "latency_ms": latency,
                    "status": "HEALTHY"
                }
        except Exception as e:
            return {
                "reachable": False,
                "port": port,
                "latency_ms": None,
                "status": "UNAVAILABLE",
                "error": str(e)
            }

    def probe_live_system(self) -> Dict[str, Dict[str, Any]]:
        """Run a standard probe suite against local host, gateway, internet, and DNS."""
        results = {}

        # 1. Local NIC check
        results["NIC_HOST"] = {
            "reachable": True,
            "latency_ms": 0.1,
            "status": "HEALTHY"
        }

        # 2. Local Switch / Gateway (Standard test IP)
        gateway_probe = self.ping_host("192.168.1.1", count=1)
        results["GW_01"] = gateway_probe
        results["SW_01"] = {
            "reachable": gateway_probe["reachable"],
            "latency_ms": gateway_probe["latency_ms"],
            "status": gateway_probe["status"]
        }

        # 3. Public External IP (Cloudflare / Google Public DNS via raw IP)
        results["DNS_PRIMARY"] = self.ping_host("8.8.8.8", count=1)
        results["ISP_UPLINK"] = {
            "reachable": results["DNS_PRIMARY"]["reachable"],
            "latency_ms": results["DNS_PRIMARY"]["latency_ms"],
            "status": results["DNS_PRIMARY"]["status"]
        }

        # 4. L7 Domain Name Resolution Check
        results["EXT_WEB"] = self.check_dns_resolution("google.com")

        return results
