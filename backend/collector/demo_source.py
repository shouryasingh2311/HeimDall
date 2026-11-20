"""
Deterministic Multi-Node Telemetry Demo Source.

Owned by Member 3 (feat/fixtures-validation).
Fulfills SIMU-01, SIMU-05, SIMU-06, SIMU-07, SIMU-08, SIMU-09.
Implements the local demo source per .planning/CONTRACTS.md and .planning/MEMBER_3_VALIDATION.md.

Features:
- Four configured dependent roles: Load Balancer (lb-01), API (api-01), Auth (auth-01), DB (db-01).
- One independent control source: Worker (worker-01).
- Two configured tenants: tenant-alpha and tenant-beta for isolation testing.
- Two-second ticks with seeded bounded pseudorandom variation for reproducible runs.
- Controllable fault injection for validation scenarios (CPU spike, network degradation, auth burst).
- Pure state tracking: no network calls, no database mutations, fully testable.
"""

from __future__ import annotations

import datetime
import random
import uuid
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Dict, List, Optional


@dataclass
class RawEvent:
    """
    Local-only raw event input shape per CONTRACTS.md.
    Raw fields (raw_text, source_ip, username, auth_success) stay strictly local.
    """
    source_key: str
    tenant_id: str
    collector_id: str
    input_id: str
    event_time_utc: str
    source_timezone: str = "UTC"
    kind: str = "metric"  # "metric" or "auth"
    metrics: Optional[Dict[str, Any]] = None
    raw_text: Optional[str] = None
    source_ip: Optional[str] = None
    username: Optional[str] = None
    auth_success: Optional[bool] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_key": self.source_key,
            "tenant_id": self.tenant_id,
            "collector_id": self.collector_id,
            "input_id": self.input_id,
            "event_time_utc": self.event_time_utc,
            "source_timezone": self.source_timezone,
            "kind": self.kind,
            "metrics": self.metrics,
            "raw_text": self.raw_text,
            "source_ip": self.source_ip,
            "username": self.username,
            "auth_success": self.auth_success,
        }


@dataclass
class SourceNodeConfig:
    node_id: str
    role: str
    depends_on: List[str] = field(default_factory=list)
    base_cpu: float = 20.0
    base_memory: float = 45.0
    base_disk: float = 48.0
    base_latency_ms: float = 12.0
    memory_limit_mb: int = 1024


class DemoSource:
    """
    Deterministic telemetry generator for 2 tenants and 5 node roles.
    Produces RawEvent instances matching CONTRACTS.md.
    """

    NODE_SPECS: List[SourceNodeConfig] = [
        SourceNodeConfig("lb-01", "load_balancer", depends_on=["api-01"], base_cpu=18.0, base_latency_ms=8.0),
        SourceNodeConfig("api-01", "api", depends_on=["auth-01", "db-01"], base_cpu=28.0, base_latency_ms=15.0),
        SourceNodeConfig("auth-01", "auth", depends_on=["db-01"], base_cpu=22.0, base_latency_ms=10.0),
        SourceNodeConfig("db-01", "database", depends_on=[], base_cpu=32.0, base_latency_ms=5.0),
        SourceNodeConfig("worker-01", "control", depends_on=[], base_cpu=15.0, base_latency_ms=2.0),
    ]

    TENANTS = ["tenant-alpha", "tenant-beta"]

    def __init__(self, seed: int = 42, run_id: Optional[str] = None):
        self.seed = seed
        self.rng = random.Random(seed)
        self.run_id = run_id or f"demo-{uuid.uuid4().hex[:8]}"
        self.sequence_counters: Dict[str, int] = {}
        self.active_injections: Dict[str, Dict[str, Any]] = {}
        # Dynamic memory allocation state for Scenario 8 (remediation testing)
        self.memory_capacities: Dict[str, int] = {
            node.node_id: node.memory_limit_mb for node in self.NODE_SPECS
        }

    def _next_input_id(self, tenant_id: str, node_id: str) -> str:
        key = f"{tenant_id}:{node_id}"
        seq = self.sequence_counters.get(key, 0) + 1
        self.sequence_counters[key] = seq
        return f"{self.run_id}-{tenant_id}-{node_id}-{seq:06d}"

    def inject_cpu_spike(self, tenant_id: str, node_id: str, target_cpu: float = 88.5, duration_ticks: int = 10) -> None:
        """Inject sustained CPU anomaly for Scenario 5 / 6."""
        key = f"{tenant_id}:{node_id}"
        self.active_injections[key] = {
            "type": "cpu_spike",
            "target_cpu": target_cpu,
            "remaining_ticks": duration_ticks,
        }

    def inject_network_degradation(
        self,
        tenant_id: str,
        node_id: str = "lb-01",
        packet_loss_pct: float = 18.0,
        latency_ms: float = 240.0,
        duration_ticks: int = 10,
    ) -> None:
        """Inject network degradation on node and cascade impact to downstream dependencies (Scenario 4)."""
        key = f"{tenant_id}:{node_id}"
        self.active_injections[key] = {
            "type": "network_degradation",
            "packet_loss_pct": packet_loss_pct,
            "latency_ms": latency_ms,
            "remaining_ticks": duration_ticks,
        }

    def scale_container_memory(self, node_id: str, new_capacity_mb: int) -> int:
        """Remediation helper action for Scenario 8 (SCALE_CONTAINER_MEMORY)."""
        prev = self.memory_capacities.get(node_id, 1024)
        self.memory_capacities[node_id] = new_capacity_mb
        return prev

    def generate_tick(
        self,
        tick_time: Optional[datetime.datetime] = None,
        tenants: Optional[List[str]] = None,
    ) -> List[RawEvent]:
        """
        Produce one batch of RawEvents across all configured nodes for the active tenants.
        Called once every 2 seconds.
        """
        if tick_time is None:
            tick_time = datetime.datetime.now(datetime.timezone.utc)

        time_str = tick_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        target_tenants = tenants or self.TENANTS
        events: List[RawEvent] = []

        for tenant_id in target_tenants:
            collector_id = f"collector-{tenant_id.split('-')[-1]}"

            # Check network degradation on lb-01 for cascading downstream effects
            lb_key = f"{tenant_id}:lb-01"
            lb_degraded = lb_key in self.active_injections and self.active_injections[lb_key]["type"] == "network_degradation"

            for spec in self.NODE_SPECS:
                key = f"{tenant_id}:{spec.node_id}"
                inj = self.active_injections.get(key)

                # Base noise (+/- 2.5%)
                jitter = self.rng.uniform(-2.5, 2.5)

                # CPU computation
                if inj and inj["type"] == "cpu_spike":
                    cpu_pct = min(100.0, max(0.0, inj["target_cpu"] + self.rng.uniform(-1.0, 1.0)))
                else:
                    cpu_pct = min(100.0, max(0.0, spec.base_cpu + jitter))

                # Memory computation (adjusted by dynamic capacity in Scenario 8)
                cap = self.memory_capacities.get(spec.node_id, spec.memory_limit_mb)
                # When capacity increases from 1024 to 2048 MB, memory_pct effectively drops
                utilization_ratio = (spec.memory_limit_mb / cap)
                base_mem = spec.base_memory * utilization_ratio
                memory_pct = min(100.0, max(0.0, base_mem + jitter * 0.5))

                # Disk
                disk_used_pct = min(100.0, max(0.0, spec.base_disk + self.rng.uniform(-0.1, 0.1)))

                # Latency & Packet loss
                if inj and inj["type"] == "network_degradation":
                    latency_ms = max(0.0, inj["latency_ms"] + self.rng.uniform(-10.0, 10.0))
                    packet_loss_pct = min(100.0, max(0.0, inj["packet_loss_pct"] + self.rng.uniform(-1.0, 1.0)))
                    service_available = packet_loss_pct < 25.0
                elif lb_degraded and "lb-01" in spec.depends_on or (lb_degraded and spec.node_id == "api-01"):
                    # Cascading dependency impact from degraded LB to API
                    latency_ms = max(0.0, spec.base_latency_ms + 140.0 + self.rng.uniform(-15.0, 15.0))
                    packet_loss_pct = min(100.0, max(0.0, 4.0 + self.rng.uniform(-0.5, 1.0)))
                    service_available = True
                else:
                    latency_ms = max(0.0, spec.base_latency_ms + self.rng.uniform(-1.5, 1.5))
                    packet_loss_pct = 0.0
                    service_available = True

                # Network byte rates (1 - 5 MB/s with jitter)
                net_tx_bps = int(max(0, 1_500_000 + self.rng.uniform(-200_000, 300_000)))
                net_rx_bps = int(max(0, 1_200_000 + self.rng.uniform(-150_000, 250_000)))
                disk_read_bps = int(max(0, 500_000 + self.rng.uniform(-50_000, 50_000)))
                disk_write_bps = int(max(0, 300_000 + self.rng.uniform(-30_000, 30_000)))

                # Tick down active injection
                if inj:
                    inj["remaining_ticks"] -= 1
                    if inj["remaining_ticks"] <= 0:
                        del self.active_injections[key]

                metrics = {
                    "cpu_pct": round(cpu_pct, 2),
                    "memory_pct": round(memory_pct, 2),
                    "disk_used_pct": round(disk_used_pct, 2),
                    "disk_read_bps": disk_read_bps,
                    "disk_write_bps": disk_write_bps,
                    "net_tx_bps": net_tx_bps,
                    "net_rx_bps": net_rx_bps,
                    "latency_ms": round(latency_ms, 2),
                    "packet_loss_pct": round(packet_loss_pct, 2),
                    "service_available": service_available,
                    "connectivity": True,
                }

                input_id = self._next_input_id(tenant_id, spec.node_id)
                event = RawEvent(
                    source_key=f"{tenant_id}:{spec.node_id}",
                    tenant_id=tenant_id,
                    collector_id=collector_id,
                    input_id=input_id,
                    event_time_utc=time_str,
                    source_timezone="UTC",
                    kind="metric",
                    metrics=metrics,
                    raw_text=f"syslog: node={spec.node_id} role={spec.role} load_ok=true",
                )
                events.append(event)

        return events

    def generate_auth_failure_event(
        self,
        tenant_id: str,
        node_id: str = "auth-01",
        username: str = "admin",
        source_ip: str = "198.51.100.42",
        raw_reason: str = "invalid password attempt",
        event_time: Optional[datetime.datetime] = None,
    ) -> RawEvent:
        """
        Produce a single raw authentication failure event.
        Used for Scenario 3 (exercising local 5-failure threshold analyzer).
        """
        if event_time is None:
            event_time = datetime.datetime.now(datetime.timezone.utc)
        time_str = event_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        collector_id = f"collector-{tenant_id.split('-')[-1]}"
        input_id = self._next_input_id(tenant_id, node_id)

        return RawEvent(
            source_key=f"{tenant_id}:{node_id}",
            tenant_id=tenant_id,
            collector_id=collector_id,
            input_id=input_id,
            event_time_utc=time_str,
            source_timezone="UTC",
            kind="auth",
            metrics=None,
            raw_text=f"sshd[1024]: Failed password for {username} from {source_ip} port 52314 ssh2: {raw_reason}",
            source_ip=source_ip,
            username=username,
            auth_success=False,
        )

    async def stream(
        self,
        interval_seconds: float = 2.0,
        max_ticks: Optional[int] = None,
    ) -> AsyncGenerator[List[RawEvent], None]:
        """
        Async streaming generator yielding a batch of events every interval_seconds.
        """
        import asyncio
        ticks = 0
        while max_ticks is None or ticks < max_ticks:
            batch = self.generate_tick()
            yield batch
            ticks += 1
            if max_ticks is not None and ticks >= max_ticks:
                break
            await asyncio.sleep(interval_seconds)
