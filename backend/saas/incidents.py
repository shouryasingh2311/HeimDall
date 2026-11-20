"""Tenant-scoped anomaly evidence and incident lifecycle."""

from collections import defaultdict
from dataclasses import asdict
from datetime import timedelta
import json
from uuid import uuid4

from backend.saas.detector import Baseline, Signal, evaluate_metrics
from backend.shared.models import MetadataPayload, parse_utc, utc_now, utc_text

SCHEMA = """
CREATE TABLE IF NOT EXISTS aiops_baseline (
    tenant_id TEXT NOT NULL, source_id TEXT NOT NULL, state TEXT NOT NULL,
    PRIMARY KEY (tenant_id, source_id)
);
CREATE TABLE IF NOT EXISTS incident (
    id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id TEXT NOT NULL, incident_id TEXT NOT NULL,
    group_key TEXT NOT NULL, category TEXT NOT NULL, severity TEXT NOT NULL, status TEXT NOT NULL,
    created_at TEXT NOT NULL, last_event TEXT NOT NULL, UNIQUE (tenant_id, incident_id)
);
CREATE INDEX IF NOT EXISTS incident_groups ON incident (tenant_id, group_key, category, last_event);
CREATE INDEX IF NOT EXISTS incident_listing ON incident (tenant_id, id);
CREATE TABLE IF NOT EXISTS incident_source (
    tenant_id TEXT NOT NULL, incident_id TEXT NOT NULL, source_id TEXT NOT NULL,
    normal_count INTEGER NOT NULL DEFAULT 0, last_normal TEXT,
    PRIMARY KEY (tenant_id, incident_id, source_id),
    FOREIGN KEY (tenant_id, incident_id) REFERENCES incident (tenant_id, incident_id)
);
CREATE INDEX IF NOT EXISTS incident_source_lookup ON incident_source (tenant_id, source_id);
CREATE TABLE IF NOT EXISTS alert (
    id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, incident_id TEXT NOT NULL, payload_uuid TEXT NOT NULL,
    source_id TEXT NOT NULL, metric TEXT NOT NULL, observed REAL NOT NULL, baseline_mean REAL,
    baseline_std REAL, z_score REAL, event_time TEXT NOT NULL, breach_at TEXT NOT NULL, created_at TEXT NOT NULL,
    UNIQUE (tenant_id, payload_uuid, metric),
    FOREIGN KEY (tenant_id, incident_id) REFERENCES incident (tenant_id, incident_id),
    FOREIGN KEY (tenant_id, payload_uuid) REFERENCES metadata (tenant_id, payload_uuid)
);
CREATE INDEX IF NOT EXISTS alert_members ON alert (tenant_id, incident_id, event_time);
CREATE INDEX IF NOT EXISTS alert_timing ON alert (tenant_id, created_at);
"""


class Topology:
    def __init__(self, graph: dict[str, list[str]]):
        neighbors = {source: set(deps) for source, deps in graph.items()}
        for source, deps in graph.items():
            for upstream in deps:
                neighbors.setdefault(upstream, set()).add(source)
        self.groups = {}
        for source in neighbors:
            if source not in self.groups:
                group = self.reachable(source, neighbors) | {source}
                self.groups.update(dict.fromkeys(group, min(group)))
        self.upstream = {source: self.reachable(source, graph) - {source} for source in graph}

    @staticmethod
    def reachable(source, graph):
        visited = set()
        pending = list(graph.get(source, ()))
        while pending:
            item = pending.pop()
            if item not in visited:
                visited.add(item)
                pending.extend(graph.get(item, ()))
        return visited


class IncidentEngine:
    def __init__(self, storage, settings):
        self.storage = storage
        self.db = storage.db
        self.policy = settings.health
        self.topologies = {tenant: Topology(graph) for tenant, graph in settings.dependencies.items()}
        self.empty_topology = Topology({})

    async def analyze_locked(self, payload: MetadataPayload, timestamp: str) -> str:
        """Run inside the same transaction as the accepted metadata row."""
        if payload.security is not None:
            signal = Signal("failed_attempts_count", payload.security.failed_attempts_count, timestamp, "critical")
            await self.raise_alerts(payload, timestamp, [signal], "security",
                                    f"{payload.source_id}:{payload.security.attacker_id}")
            return "live"
        key = (payload.tenant_id, payload.source_id)
        rows = await self.db.execute_fetchall(
            "SELECT state FROM aiops_baseline WHERE tenant_id=? AND source_id=?", key,
        )
        baselines = {metric: Baseline(**state) for metric, state in json.loads(rows[0][0]).items()} if rows else {}
        signals, normal, ready = evaluate_metrics(payload, self.policy, baselines, timestamp)
        await self.db.execute(
            """INSERT INTO aiops_baseline VALUES (?, ?, ?)
               ON CONFLICT (tenant_id, source_id) DO UPDATE SET state=excluded.state""",
            (*key, json.dumps({name: asdict(state) for name, state in baselines.items()})),
        )
        if signals:
            topology = self.topologies.get(payload.tenant_id, self.empty_topology)
            await self.raise_alerts(payload, timestamp, signals, "infrastructure",
                                    topology.groups.get(payload.source_id, payload.source_id))
        # A sample can contain a new alert and still be relevant to an older
        # incident. Missing or deviant signals cannot advance a recovery streak.
        await self.recover(payload, timestamp, normal)
        return "live" if signals or ready else "warming_up"

    async def raise_alerts(self, payload, timestamp, signals, category, group):
        tenant = payload.tenant_id
        event = parse_utc(timestamp)
        rows = await self.db.execute_fetchall(
            """SELECT incident_id, severity FROM incident WHERE tenant_id=? AND category=? AND group_key=?
               AND status!='resolved' AND last_event BETWEEN ? AND ? ORDER BY last_event DESC, id DESC LIMIT 1""",
            (tenant, category, group, utc_text(event - timedelta(seconds=60)), utc_text(event + timedelta(seconds=60))),
        )
        severity = "critical" if any(signal.severity == "critical" for signal in signals) else "warning"
        created_at = utc_text(utc_now())
        if rows:
            incident = rows[0]["incident_id"]
            severity = "critical" if rows[0]["severity"] == "critical" else severity
            await self.db.execute(
                """UPDATE incident SET status='open', severity=?, last_event=max(last_event, ?)
                   WHERE tenant_id=? AND incident_id=?""", (severity, timestamp, tenant, incident),
            )
            await self.db.execute(
                "UPDATE incident_source SET normal_count=0,last_normal=NULL WHERE tenant_id=? AND incident_id=?",
                (tenant, incident),
            )
        else:
            incident = str(uuid4())
            await self.db.execute(
                """INSERT INTO incident (tenant_id, incident_id, category, group_key, severity, status, created_at, last_event)
                   VALUES (?, ?, ?, ?, ?, 'open', ?, ?)""", (tenant, incident, category, group, severity, created_at, timestamp),
            )
        await self.db.execute(
            "INSERT OR IGNORE INTO incident_source (tenant_id,incident_id,source_id) VALUES (?,?,?)",
            (tenant, incident, payload.source_id),
        )
        await self.db.executemany(
            """INSERT INTO alert (id, tenant_id, incident_id, payload_uuid, source_id, metric,
                                  observed, baseline_mean, baseline_std, z_score, event_time, breach_at, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            [(str(uuid4()), tenant, incident, payload.payload_uuid, payload.source_id, signal.metric,
              signal.observed, signal.baseline_mean, signal.baseline_std, signal.z_score,
              timestamp, signal.breach_at, created_at) for signal in signals],
        )

    async def recover(self, payload, timestamp, normal):
        tenant, source = payload.tenant_id, payload.source_id
        rows = await self.db.execute_fetchall(
            """SELECT i.incident_id, s.last_normal, a.metric FROM incident_source AS s
               JOIN incident AS i USING (tenant_id, incident_id)
               JOIN alert AS a USING (tenant_id, incident_id, source_id)
               WHERE s.tenant_id=? AND s.source_id=? AND i.category='infrastructure'
               AND i.status!='resolved' AND i.last_event < ? GROUP BY i.incident_id, a.metric""",
            (tenant, source, timestamp),
        )
        requirements = defaultdict(set)
        last_normal = {}
        for row in rows:
            requirements[row["incident_id"]].add(row["metric"])
            last_normal[row["incident_id"]] = row["last_normal"]
        fresh_since = utc_text(utc_now() - timedelta(seconds=30))
        for incident, required in requirements.items():
            healthy = required <= normal
            consecutive = healthy and (last_normal[incident] or "") >= fresh_since
            await self.db.execute(
                """UPDATE incident_source SET normal_count=CASE WHEN ? THEN min(5, normal_count+1) ELSE ? END,
                   last_normal=? WHERE tenant_id=? AND incident_id=? AND source_id=?""",
                (consecutive, int(healthy), timestamp if healthy else None, tenant, incident, source),
            )
            await self.db.execute(
                """UPDATE incident SET status=(SELECT CASE
                       WHEN min(CASE WHEN last_normal > ? THEN normal_count ELSE 0 END)>=5 THEN 'resolved'
                       WHEN max(CASE WHEN last_normal > ? THEN normal_count ELSE 0 END)>0 THEN 'recovering'
                       ELSE 'open' END FROM incident_source WHERE tenant_id=? AND incident_id=?)
                   WHERE tenant_id=? AND incident_id=?""",
                (fresh_since, fresh_since, tenant, incident, tenant, incident),
            )

    async def list(self, tenant: str, before: int, limit: int):
        async with self.storage.lock:
            rows = await self.db.execute_fetchall(
                "SELECT * FROM incident WHERE tenant_id=? AND id<? ORDER BY id DESC LIMIT ?", (tenant, before, limit + 1),
            )
            items = [await self.detail_locked(row) for row in rows[:limit]]
        fields = {"incident_id", "severity", "status", "template_title", "source_ids", "evidence_score", "created_at_utc"}
        return {
            "items": [{k: v for k, v in item.items() if k in fields} for item in items],
            "next_cursor": str(rows[limit - 1]["id"]) if len(rows) > limit else None,
        }

    async def detail(self, tenant: str, incident_id: str):
        async with self.storage.lock:
            rows = await self.db.execute_fetchall(
                "SELECT * FROM incident WHERE tenant_id=? AND incident_id=?", (tenant, incident_id),
            )
            return await self.detail_locked(rows[0]) if rows else None

    async def detail_locked(self, incident):
        rows = await self.db.execute_fetchall(
            "SELECT * FROM alert WHERE tenant_id=? AND incident_id=? ORDER BY event_time, id",
            (incident["tenant_id"], incident["incident_id"]),
        )
        topology = self.topologies.get(incident["tenant_id"], self.empty_topology)
        return incident_evidence(incident, rows, topology)


def incident_evidence(incident, rows, topology):
    fields = ("payload_uuid", "source_id", "metric", "observed", "baseline_mean", "baseline_std", "z_score")
    signals = [{**{field: row[field] for field in fields}, "event_time_utc": row["event_time"]} for row in rows]
    bounds = {}
    for row in rows:
        source, timestamp = row["source_id"], row["event_time"]
        bounds[source] = (bounds.get(source, (timestamp,))[0], timestamp)
    security = incident["category"] == "security"
    linked = [(upstream, consumer) for consumer in sorted(bounds)
              for upstream in sorted(topology.upstream.get(consumer, set()) & bounds.keys())] if not security else []
    ordered = [(upstream, consumer) for upstream, consumer in linked if bounds[upstream][0] <= bounds[consumer][1]]
    metrics = len({row["metric"] for row in rows})
    score = min(100, 30 * min(metrics, 2) + 20 * bool(linked) + 20 * bool(ordered))
    reasoning = [
        f"{len(rows)} persisted alert signals from {len(bounds)} monitored sources.",
        f"Score inputs: {metrics} distinct metrics, dependency={int(bool(linked))}, temporal order={int(bool(ordered))}.",
    ]
    if ordered:
        upstream, consumer = min(ordered, key=lambda pair: (bounds[pair[0]][0], pair))
        cause = f"An anomaly at {upstream} may have contributed to the signal at dependent source {consumer}."
        reasoning.append("The dependency is configured and the observed timestamps are consistent with that direction.")
    elif security:
        cause = "The local collector observed a burst of failed logins from one pseudonymous origin."
    else:
        cause = "The flagged metrics identify where to investigate. No upstream cause is established by the observed signals."
    return {
        "incident_id": incident["incident_id"], "severity": incident["severity"], "status": incident["status"],
        "template_title": "Repeated failed logins" if security else "Infrastructure anomaly",
        "created_at_utc": incident["created_at"], "source_ids": sorted(bounds), "alert_ids": [row["id"] for row in rows],
        "likely_cause": cause, "evidence_score": score,
        "score_method": "Heuristic: min(100, 30 × min(distinct metrics, 2) + 20 × configured dependency + 20 × temporal order)",
        "contributing_signals": signals, "reasoning_steps": reasoning,
        "recommended_action": ("Review local authentication policy and confirm the activity with the system owner."
                               if security else "Inspect the flagged metrics and compare the affected services with their dependencies."),
        "proposal_status": "none",
    }
