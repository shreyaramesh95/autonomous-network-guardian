"""The snapshot the diagnosis engine reasons over.

An ``Observation`` is the latest known state of every device plus the DNS and
internet checks. It can be built two ways:

* ``from_provider`` - probe now, in memory (used by tests and ad-hoc diagnosis)
* ``from_db``       - read the rows the monitoring engine already stored
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

CLIENT_ROLES = ("Client", "Service", "Peripheral")


@dataclass
class DeviceObs:
    id: int
    name: str
    ip: str
    role: str
    depends_on: Optional[int]
    reachable: bool
    latency_ms: Optional[float]
    packet_loss_pct: float

    @property
    def is_client(self) -> bool:
        return self.role in CLIENT_ROLES

    @property
    def is_gateway(self) -> bool:
        return self.role == "Gateway"


@dataclass
class Observation:
    devices: list[DeviceObs]
    dns_ok: bool
    internet_ok: bool
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    dns_detail: str = ""
    internet_detail: str = ""

    # -- lookups ---------------------------------------------------------
    @property
    def gateway(self) -> Optional[DeviceObs]:
        return next((d for d in self.devices if d.is_gateway), None)

    @property
    def clients(self) -> list[DeviceObs]:
        return [d for d in self.devices if d.is_client]

    @property
    def unreachable(self) -> list[DeviceObs]:
        return [d for d in self.devices if not d.reachable]

    @property
    def unreachable_non_gateway(self) -> list[DeviceObs]:
        return [d for d in self.devices if not d.reachable and not d.is_gateway]

    @property
    def gateway_reachable(self) -> bool:
        gw = self.gateway
        return gw is None or gw.reachable

    def dependents_of(self, device_id: int) -> list[DeviceObs]:
        return [d for d in self.devices if d.depends_on == device_id]

    # -- builders ------------------------------------------------------------
    @classmethod
    def from_provider(cls, devices, provider, config) -> "Observation":
        get = config.get if hasattr(config, "get") else config.__getitem__
        dev_obs: list[DeviceObs] = []
        for d in devices:
            r = provider.probe_device(d["ip_address"])
            dev_obs.append(DeviceObs(
                id=d["id"], name=d["name"], ip=d["ip_address"], role=d["role"],
                depends_on=d["depends_on"], reachable=r.reachable,
                latency_ms=r.latency_ms, packet_loss_pct=r.packet_loss_pct,
            ))
        dns = provider.check_dns(get("DNS_TEST_HOSTNAME"))
        inet = provider.check_internet(get("INTERNET_TEST_IP"), get("INTERNET_TEST_PORT"))
        return cls(devices=dev_obs, dns_ok=dns.reachable, internet_ok=inet.reachable,
                   dns_detail=dns.detail, internet_detail=inet.detail)

    @classmethod
    def from_db(cls, conn) -> "Observation":
        from ..database import models as m

        latest = m.latest_measurements(conn)
        dev_obs: list[DeviceObs] = []
        for d in m.list_devices(conn):
            row = latest.get(d["id"])
            if row is None:
                dev_obs.append(DeviceObs(d["id"], d["name"], d["ip_address"], d["role"],
                                         d["depends_on"], reachable=True,
                                         latency_ms=None, packet_loss_pct=0.0))
            else:
                dev_obs.append(DeviceObs(
                    d["id"], d["name"], d["ip_address"], d["role"], d["depends_on"],
                    reachable=bool(row["reachable"]), latency_ms=row["latency"],
                    packet_loss_pct=row["packet_loss"] or 0.0,
                ))
        dns = m.latest_service_check(conn, "dns")
        inet = m.latest_service_check(conn, "internet")
        return cls(
            devices=dev_obs,
            dns_ok=bool(dns["reachable"]) if dns else True,
            internet_ok=bool(inet["reachable"]) if inet else True,
            dns_detail=dns["detail"] if dns else "",
            internet_detail=inet["detail"] if inet else "",
        )
