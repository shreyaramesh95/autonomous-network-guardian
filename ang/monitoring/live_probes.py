"""Real network probes.

Best-effort and secondary to simulation mode: ICMP from an unprivileged process
is unreliable on Windows, so device probing shells out to the system ``ping``
command and parses its output. DNS and internet checks use plain sockets.
"""
from __future__ import annotations

import platform
import re
import socket
import subprocess
import time

from .probes import ProbeProvider, ProbeResult, ServiceResult

_IS_WINDOWS = platform.system().lower().startswith("win")

# "Lost = 1 (20% loss)"  /  "5 received, 20% packet loss"
_LOSS_RE = re.compile(r"(\d+(?:\.\d+)?)%\s*(?:packet )?loss", re.IGNORECASE)
# "Average = 12ms"  /  "rtt min/avg/max/mdev = 1.1/2.2/3.3/0.4 ms"
_AVG_WIN_RE = re.compile(r"Average\s*=\s*(\d+)ms", re.IGNORECASE)
_AVG_NIX_RE = re.compile(r"=\s*[\d.]+/([\d.]+)/[\d.]+/[\d.]+\s*ms")


class LiveProbes(ProbeProvider):
    def __init__(self, config):
        self.count = int(config.get("PING_COUNT", 5))
        self.timeout_ms = int(config.get("PING_TIMEOUT_MS", 1000))

    # -- devices ---------------------------------------------------------
    def probe_device(self, ip: str) -> ProbeResult:
        if _IS_WINDOWS:
            cmd = ["ping", "-n", str(self.count), "-w", str(self.timeout_ms), ip]
        else:
            cmd = ["ping", "-c", str(self.count),
                   "-W", str(max(1, self.timeout_ms // 1000)), ip]
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=(self.timeout_ms / 1000) * self.count + 5,
            )
        except (subprocess.TimeoutExpired, OSError):
            return ProbeResult(reachable=False, latency_ms=None, packet_loss_pct=100.0)

        out = (proc.stdout or "") + (proc.stderr or "")
        loss_m = _LOSS_RE.search(out)
        loss = float(loss_m.group(1)) if loss_m else (0.0 if proc.returncode == 0 else 100.0)

        avg_m = _AVG_WIN_RE.search(out) or _AVG_NIX_RE.search(out)
        latency = float(avg_m.group(1)) if avg_m else None

        reachable = loss < 100.0 and proc.returncode == 0
        if not reachable:
            latency = None
        return ProbeResult(reachable=reachable, latency_ms=latency, packet_loss_pct=loss)

    # -- DNS -----------------------------------------------------------------
    def check_dns(self, hostname: str) -> ServiceResult:
        start = time.perf_counter()
        try:
            socket.getaddrinfo(hostname, None)
        except socket.gaierror as exc:
            return ServiceResult(reachable=False, detail=f"resolution failed: {exc}")
        except OSError as exc:
            return ServiceResult(reachable=False, detail=str(exc))
        ms = (time.perf_counter() - start) * 1000
        return ServiceResult(reachable=True, latency_ms=round(ms, 1),
                             detail=f"{hostname} resolved")

    # -- internet / WAN --------------------------------------------------
    def check_internet(self, ip: str, port: int) -> ServiceResult:
        start = time.perf_counter()
        try:
            with socket.create_connection((ip, port), timeout=self.timeout_ms / 1000):
                pass
        except OSError as exc:
            return ServiceResult(reachable=False, detail=f"{ip}:{port} unreachable ({exc})")
        ms = (time.perf_counter() - start) * 1000
        return ServiceResult(reachable=True, latency_ms=round(ms, 1),
                             detail=f"{ip}:{port} reachable")
