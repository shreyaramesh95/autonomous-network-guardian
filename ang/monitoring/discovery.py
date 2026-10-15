"""LAN discovery: find real devices on the user's own Wi-Fi/network so they
can be registered and monitored instead of (or alongside) the sample topology.

Read-only and local-only: a ping sweep of the operator's own subnet plus an
ARP-table lookup. No external services are contacted. Deliberately no
reverse-DNS lookups here: ``socket.gethostbyaddr`` has no reliable way to
bound its blocking time on Windows, and a worker thread stuck in it keeps the
whole process alive at interpreter exit (``concurrent.futures`` waits for
every thread pool thread it ever created, regardless of per-call timeouts).
"""
from __future__ import annotations

import ipaddress
import platform
import re
import socket
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Optional

_IS_WINDOWS = platform.system().lower().startswith("win")

# How many hosts a single "Scan" click will probe. Large campus/corporate Wi-Fi
# networks (e.g. a /21) hand out addresses from a huge pool; scanning all of it
# would take minutes, so by default we scan the /24 around the local machine
# and let the caller widen the range explicitly if they know it.
_MAX_HOSTS_DEFAULT = 256


@dataclass
class DiscoveredHost:
    ip: str
    hostname: Optional[str] = None
    mac: Optional[str] = None
    is_self: bool = False
    is_gateway: bool = False


@dataclass
class NetworkInfo:
    local_ip: Optional[str]
    gateway_ip: Optional[str]
    netmask: Optional[str]
    scan_cidr: Optional[str]
    note: str = ""


def _local_ip() -> Optional[str]:
    """The IP this machine would use to reach the internet - no packets sent."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()


def _ipconfig_text() -> str:
    try:
        cmd = ["ipconfig"] if _IS_WINDOWS else ["ifconfig"]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        return proc.stdout or ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def _windows_gateway_and_mask(local_ip: str) -> tuple[Optional[str], Optional[str]]:
    """Parse ``ipconfig`` for the adapter whose IPv4 address matches ``local_ip``."""
    text = _ipconfig_text()
    blocks = re.split(r"\r?\n\r?\n", text)
    for block in blocks:
        if local_ip not in block:
            continue
        gw_m = re.search(r"Default Gateway[ .]*:\s*([\d.]+)", block)
        mask_m = re.search(r"Subnet Mask[ .]*:\s*([\d.]+)", block)
        gw = gw_m.group(1) if gw_m and gw_m.group(1) else None
        mask = mask_m.group(1) if mask_m else None
        return gw, mask
    return None, None


def get_network_info(cidr_override: Optional[str] = None) -> NetworkInfo:
    local_ip = _local_ip()
    gateway_ip, netmask = (None, None)
    if local_ip and _IS_WINDOWS:
        gateway_ip, netmask = _windows_gateway_and_mask(local_ip)

    note = ""
    scan_cidr = cidr_override
    # Prefer anchoring the default /24 on the gateway's address, not this
    # machine's: on a large DHCP pool (e.g. a /21 campus Wi-Fi) the router and
    # this machine can land in different /24s within the same real subnet,
    # and the router's side is where other devices are most likely to be.
    anchor_ip = gateway_ip or local_ip
    if not scan_cidr:
        if local_ip and netmask:
            try:
                iface = ipaddress.ip_interface(f"{local_ip}/{netmask}")
                net = iface.network
                if net.num_addresses > _MAX_HOSTS_DEFAULT:
                    octets = (anchor_ip or local_ip).split(".")
                    scan_cidr = f"{'.'.join(octets[:3])}.0/24"
                    note = (f"Actual network is {net} ({net.num_addresses} addresses); "
                            f"scanning the /24 around the router by default. "
                            f"Pass cidr= to scan a different range.")
                else:
                    scan_cidr = str(net)
            except ValueError:
                pass
        if not scan_cidr and anchor_ip:
            octets = anchor_ip.split(".")
            scan_cidr = f"{'.'.join(octets[:3])}.0/24"
            note = "Could not determine the real subnet mask; assuming a /24."

    return NetworkInfo(local_ip=local_ip, gateway_ip=gateway_ip, netmask=netmask,
                        scan_cidr=scan_cidr, note=note)


def _ping_once(ip: str, timeout_ms: int = 400) -> bool:
    if _IS_WINDOWS:
        cmd = ["ping", "-n", "1", "-w", str(timeout_ms), ip]
    else:
        cmd = ["ping", "-c", "1", "-W", str(max(1, timeout_ms // 1000)), ip]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                               timeout=(timeout_ms / 1000) + 2)
    except (subprocess.TimeoutExpired, OSError):
        return False
    return proc.returncode == 0


def _arp_table() -> dict[str, str]:
    """Best-effort IP -> MAC map from the OS ARP cache (already-contacted hosts)."""
    out = {}
    try:
        cmd = ["arp", "-a"]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        for line in (proc.stdout or "").splitlines():
            m = re.search(r"(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F-:]{11,17})", line)
            if m:
                out[m.group(1)] = m.group(2).lower()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return out


def scan_lan(cidr: str, local_ip: Optional[str] = None, gateway_ip: Optional[str] = None,
             max_workers: int = 32, timeout_ms: int = 400) -> list[DiscoveredHost]:
    """Ping-sweep ``cidr`` and return the hosts that answered."""
    try:
        network = ipaddress.ip_network(cidr, strict=False)
    except ValueError:
        return []

    hosts = list(network.hosts())
    if len(hosts) > 1024:
        hosts = hosts[:1024]

    found: list[str] = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_ping_once, str(h), timeout_ms): str(h) for h in hosts}
        for fut in as_completed(futures):
            ip = futures[fut]
            try:
                if fut.result():
                    found.append(ip)
            except Exception:
                pass

    arp = _arp_table()
    results = []
    for ip in sorted(found, key=lambda s: tuple(int(p) for p in s.split("."))):
        results.append(DiscoveredHost(
            ip=ip,
            mac=arp.get(ip),
            is_self=(ip == local_ip),
            is_gateway=(ip == gateway_ip),
        ))
    return results
