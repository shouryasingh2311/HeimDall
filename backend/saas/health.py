"""Evaluate source and collector health and record observed state changes."""

import asyncio
from datetime import datetime
import json
from typing import TYPE_CHECKING

from backend.shared.config import HealthPolicy
from backend.shared.models import CollectorHeartbeat, Metrics, parse_utc, utc_now, utc_text

if TYPE_CHECKING:
    from backend.saas.storage import Storage

STATES = ("Excellent", "Good", "Fair", "Poor")
DEFAULT_EXPECTED = (
    "cpu_pct", "memory_pct", "disk_used_pct", "latency_ms",
    "packet_loss_pct", "service_available", "connectivity",
)
SCHEMA = """
CREATE TABLE IF NOT EXISTS health_current (
    tenant_id TEXT NOT NULL, entity_type TEXT NOT NULL, entity_id TEXT NOT NULL, state TEXT NOT NULL,
    PRIMARY KEY (tenant_id, entity_type, entity_id)
);
CREATE TABLE IF NOT EXISTS health_transition (
    id INTEGER PRIMARY KEY, tenant_id TEXT NOT NULL, entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL, from_state TEXT NOT NULL, to_state TEXT NOT NULL,
    reasons TEXT NOT NULL, observed_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS health_transition_tenant ON health_transition (tenant_id, id);
CREATE TABLE IF NOT EXISTS offline_observation (
    tenant_id TEXT NOT NULL, collector_id TEXT NOT NULL, heartbeat_at TEXT NOT NULL, observed_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, collector_id, heartbeat_at)
);
CREATE INDEX IF NOT EXISTS offline_observation_time ON offline_observation (tenant_id, observed_at);
"""


def band(value: float | None, thresholds: list[float]) -> int:
    return sum(value >= threshold for threshold in thresholds) if value is not None else 0


def evaluate(signals: list[tuple[str, int]]) -> tuple[str, list[str]]:
    severity = max((level for _, level in signals), default=0)
    return STATES[severity], [reason for reason, level in signals if level] or ["nominal"]


def source_health(
    policy: HealthPolicy, source_id: str, metrics: Metrics, age: float,
    config_invalid: bool, risk: float | None = None,
) -> tuple[str, list[str]]:
    signals = [
        ("cpu", band(metrics.cpu_pct, policy.cpu)),
        ("memory", band(metrics.memory_pct, policy.memory)),
        ("disk", band(metrics.disk_used_pct, policy.disk)),
        ("latency", band(metrics.latency_ms, policy.latency)),
        ("packet_loss", band(metrics.packet_loss_pct, policy.packet_loss) if metrics.packet_loss_pct else 0),
        ("service_unavailable", 3 if metrics.service_available is False else 0),
        ("connectivity_down", 3 if metrics.connectivity is False else 0),
        ("security_risk", 1 + band(risk, policy.risk) if risk is not None and risk >= policy.risk[0] else 0),
        ("config_invalid", 2 if config_invalid else 0),
        ("source_expired" if age >= 55 else "source_stale", 3 if age >= 55 else 2 if age >= 30 else 0),
    ]
    expected = policy.expected_signals.get(source_id, DEFAULT_EXPECTED)
    signals.extend((f"missing_{field}", 2) for field in expected if getattr(metrics, field) is None)
    return evaluate(signals)


class HealthMonitor:
    def __init__(self, storage: "Storage", policy: HealthPolicy, sources_by_tenant: dict[str, set[str]]):
        self.storage = storage
        self.policy = policy
        self.sources_by_tenant = sources_by_tenant

    async def watch(self):
        while True:
            for tenant in self.sources_by_tenant:
                await self.snapshot(tenant)
            await asyncio.sleep(1)

    async def snapshot(self, tenant: str):
        async with self.storage.write():
            return await self.refresh_locked(tenant)

    async def refresh_locked(self, tenant: str):
        now = utc_now()
        beats, metrics, risks = await self.storage.fleet_rows(tenant, self.sources_by_tenant[tenant])
        beat_by_collector = {}
        collectors = []
        for row in beats:
            beat = CollectorHeartbeat.model_validate_json(row["body"])
            beat_by_collector[beat.collector_id] = beat
            heartbeat_time = min(parse_utc(row["generated_at"]), parse_utc(row["received_at"]))
            expired = (now - heartbeat_time).total_seconds() >= 55
            if expired:
                await self.storage.db.execute(
                    "INSERT OR IGNORE INTO offline_observation VALUES (?, ?, ?, ?)",
                    (tenant, beat.collector_id, utc_text(heartbeat_time), utc_text(now)),
                )
            health, reasons = evaluate([
                ("heartbeat_expired", 3 if expired else 0),
                ("config_invalid", 2 if beat.config_status == "invalid" else 0),
                ("cpu", band(beat.cpu_pct, self.policy.cpu)),
            ])
            collectors.append({
                "collector_id": beat.collector_id, "health": health, "reasons": reasons,
                "last_heartbeat_utc": row["generated_at"], "version": beat.version,
                "rss_mb": beat.rss_mb, "cpu_pct": beat.cpu_pct, "queue_depth": beat.queue_depth,
                "config_status": beat.config_status,
            })

        recent_risk = {}
        for row in risks:
            detail = self.storage.detail(row)
            if detail.security is not None and (now - parse_utc(detail.event_time_utc)).total_seconds() < 30:
                recent_risk[detail.source_id] = detail.security.risk_score

        sources = []
        for row in metrics:
            data = self.storage.detail(row)
            beat = beat_by_collector.get(data.collector_id)
            health, reasons = source_health(
                self.policy, data.source_id, data.metrics,
                (now - parse_utc(data.event_time_utc)).total_seconds(),
                beat is not None and beat.config_status == "invalid", recent_risk.get(data.source_id),
            )
            if data.analysis_status == "historical":
                health = "Poor"
                reasons = ["no_live_telemetry", *(reason for reason in reasons if reason != "nominal")]
            sources.append({
                "source_id": data.source_id, "collector_id": data.collector_id, "health": health,
                "reason_codes": reasons, "latest_event_time_utc": data.event_time_utc,
                "last_received_at_utc": data.received_at_utc, "metrics": data.metrics,
                "payload_uuid": data.payload_uuid,
            })
        current = await self.storage.db.execute_fetchall(
            "SELECT entity_type, entity_id, state FROM health_current WHERE tenant_id=?", (tenant,),
        )
        states = {(row["entity_type"], row["entity_id"]): row["state"] for row in current}
        changes = [
            ("collector", row["collector_id"], row["health"], row["reasons"]) for row in collectors
        ] + [
            ("source", row["source_id"], row["health"], row["reason_codes"]) for row in sources
        ]
        for kind, identity, health, reasons in changes:
            previous = states.get((kind, identity))
            if previous == health:
                continue
            await self.storage.db.execute(
                """INSERT INTO health_current VALUES (?, ?, ?, ?)
                   ON CONFLICT (tenant_id, entity_type, entity_id) DO UPDATE SET state=excluded.state""",
                (tenant, kind, identity, health),
            )
            if previous is not None:
                await self.storage.db.execute(
                    """INSERT INTO health_transition
                       (tenant_id, entity_type, entity_id, from_state, to_state, reasons, observed_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (tenant, kind, identity, previous, health, json.dumps(reasons), utc_text(now)),
                )
        return {"collectors": collectors, "sources": sources, "server_time_utc": utc_text(now)}

    async def transitions(self, tenant: str, before: int, limit: int):
        async with self.storage.lock:
            rows = await self.storage.db.execute_fetchall(
                """SELECT * FROM health_transition WHERE tenant_id=? AND id < ?
                   ORDER BY id DESC LIMIT ?""", (tenant, before, limit + 1),
            )
        return {
            "items": [{
                "transition_id": str(row["id"]), "entity_id": row["entity_id"],
                "entity_type": row["entity_type"], "from_state": row["from_state"], "to_state": row["to_state"],
                "reason_codes": json.loads(row["reasons"]), "timestamp_utc": row["observed_at"],
            } for row in rows[:limit]],
            "next_cursor": str(rows[limit - 1]["id"]) if len(rows) > limit else None,
        }
