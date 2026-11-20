"""Policy checks and durable dispatch for one simulated memory playbook."""

from datetime import timedelta
from hashlib import sha256
from uuid import uuid4

from fastapi import HTTPException

from backend.shared.models import MetadataPayload, canonical_bytes, utc_now, utc_text
from backend.shared.remediation import FACTOR, PLAYBOOK, CommandResult, DemoCommand, scaled_capacity

SCHEMA = """
CREATE TABLE IF NOT EXISTS demo_action (
    tenant_id TEXT NOT NULL, action_id TEXT NOT NULL, incident_id TEXT NOT NULL, source_id TEXT NOT NULL,
    collector_id TEXT NOT NULL, status TEXT NOT NULL, reason_code TEXT NOT NULL, created_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, action_id), UNIQUE (tenant_id, incident_id),
    FOREIGN KEY (tenant_id,incident_id) REFERENCES incident (tenant_id,incident_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_demo_action ON demo_action (tenant_id, source_id)
WHERE status IN ('proposed','approved','executing','succeeded','rollback_pending','rollback_failed');
CREATE INDEX IF NOT EXISTS demo_action_rate ON demo_action (tenant_id, source_id, created_at);
CREATE TABLE IF NOT EXISTS demo_command (
    tenant_id TEXT NOT NULL, command_id TEXT NOT NULL, action_id TEXT NOT NULL, kind TEXT NOT NULL,
    dispatched INTEGER NOT NULL DEFAULT 0, result BLOB,
    PRIMARY KEY (tenant_id, command_id), UNIQUE (tenant_id, action_id, kind),
    FOREIGN KEY (tenant_id,action_id) REFERENCES demo_action (tenant_id,action_id)
);
CREATE TABLE IF NOT EXISTS demo_audit (
    id INTEGER PRIMARY KEY, tenant_id TEXT NOT NULL, action_id TEXT NOT NULL, actor TEXT NOT NULL,
    previous_status TEXT, status TEXT NOT NULL, policy_verdict TEXT NOT NULL, reason_code TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    FOREIGN KEY (tenant_id,action_id) REFERENCES demo_action (tenant_id,action_id)
);
CREATE INDEX IF NOT EXISTS demo_audit_listing ON demo_audit (tenant_id, id);
"""

ACTIVE = ("proposed", "approved", "executing", "succeeded", "rollback_pending", "rollback_failed")
POLICY_ALLOWED = "demo_policy_allowed"
POLICY_DENIED = "policy_denied"


def public_action(row):
    return {
        "action_id": row["action_id"], "incident_id": row["incident_id"], "target_source_id": row["source_id"],
        "playbook": PLAYBOOK, "factor": FACTOR, "simulation": True,
        "policy_verdict": POLICY_DENIED if row["reason_code"] == "policy_changed" else POLICY_ALLOWED,
        "reason_code": row["reason_code"], "status": row["status"],
    }


def operator_actor(credential):
    fingerprint = sha256(f"remediation-audit:{credential.token_sha256}".encode()).hexdigest()[:16]
    return f"operator-{fingerprint}"


class Remediation:
    def __init__(self, storage, settings):
        self.storage = storage
        self.db = storage.db
        self.owners = {(c.tenant_id, source): c.collector_id for c in settings.credentials for source in c.demo_source_ids}

    async def one(self, query, params):
        rows = await self.db.execute_fetchall(query, params)
        return rows[0] if rows else None

    async def by_action(self, tenant, action_id):
        return await self.one("SELECT * FROM demo_action WHERE tenant_id=? AND action_id=?", (tenant, action_id))

    async def by_incident(self, tenant, incident_id):
        return await self.one("SELECT * FROM demo_action WHERE tenant_id=? AND incident_id=?", (tenant, incident_id))

    async def target(self, tenant, incident_id, required_source=None):
        rows = await self.db.execute_fetchall(
            """SELECT a.source_id, m.body FROM incident AS i
               JOIN alert AS a USING (tenant_id, incident_id)
               JOIN metadata AS m USING (tenant_id,payload_uuid)
               WHERE i.tenant_id=? AND i.incident_id=? AND i.status='open' AND a.metric='memory_pct'
               AND (? IS NULL OR a.source_id=?)
               ORDER BY a.event_time DESC, a.source_id""", (tenant, incident_id, required_source, required_source),
        )
        checked = set()
        for row in rows:
            source = row["source_id"]
            collector = self.owners.get((tenant, source))
            if not collector or source in checked or MetadataPayload.model_validate_json(row["body"]).simulation is not True:
                continue
            checked.add(source)
            latest = await self.one(
                """SELECT body FROM metadata WHERE tenant_id=? AND source_id=? AND event_type='metric'
                   AND analysis_status!='historical' ORDER BY event_time DESC LIMIT 1""", (tenant, source),
            )
            if latest and MetadataPayload.model_validate_json(latest["body"]).simulation is True:
                return source, collector
        return None

    async def audit(self, tenant, action_id, actor, previous, status, reason, policy=POLICY_ALLOWED):
        await self.db.execute(
            """INSERT INTO demo_audit (tenant_id,action_id,actor,previous_status,status,policy_verdict,reason_code,occurred_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (tenant, action_id, actor, previous, status, policy, reason, utc_text(utc_now())),
        )

    async def transition(self, row, actor, status, reason, policy=POLICY_ALLOWED):
        tenant, action_id = row["tenant_id"], row["action_id"]
        await self.db.execute(
            "UPDATE demo_action SET status=?, reason_code=? WHERE tenant_id=? AND action_id=?",
            (status, reason, tenant, action_id),
        )
        await self.audit(tenant, action_id, actor, row["status"], status, reason, policy)
        return await self.by_action(tenant, action_id)

    async def propose(self, credential, incident_id):
        tenant = credential.tenant_id
        async with self.storage.write():
            previous = await self.by_incident(tenant, incident_id)
            if previous:
                return public_action(previous)
            exists = await self.one("SELECT 1 FROM incident WHERE tenant_id=? AND incident_id=?", (tenant, incident_id))
            if not exists:
                raise HTTPException(404, "Incident not found")
            target = await self.target(tenant, incident_id)
            if target is None:
                raise HTTPException(409, "An active memory incident on a configured demo source is required")
            source, collector = target
            active = await self.one(
                f"""SELECT * FROM demo_action WHERE tenant_id=? AND source_id=?
                    AND status IN ({','.join('?' for _ in ACTIVE)})""", (tenant, source, *ACTIVE),
            )
            if active:
                if active["status"] != "proposed" or await self.target(tenant, active["incident_id"], source):
                    raise HTTPException(409, "This demo target already has an active action")
                await self.transition(active, "policy", "failed", "policy_changed", POLICY_DENIED)
            now = utc_now()
            rate = await self.one(
                "SELECT count(*) FROM demo_action WHERE tenant_id=? AND source_id=? AND created_at>=?",
                (tenant, source, utc_text(now - timedelta(hours=1))),
            )
            if rate[0] >= 3:
                raise HTTPException(429, "Demo target action limit reached")
            action_id = str(uuid4())
            await self.db.execute(
                "INSERT INTO demo_action VALUES (?,?,?,?,?,?,?,?)",
                (tenant, action_id, incident_id, source, collector, "proposed", "eligible_memory_incident", utc_text(now)),
            )
            await self.audit(tenant, action_id, operator_actor(credential), None, "proposed", "eligible_memory_incident")
            return public_action(await self.by_action(tenant, action_id))

    async def enqueue(self, row, kind):
        await self.db.execute(
            "INSERT INTO demo_command (tenant_id,command_id,action_id,kind) VALUES (?,?,?,?)",
            (row["tenant_id"], str(uuid4()), row["action_id"], kind),
        )

    async def approve(self, credential, action_id):
        tenant, actor = credential.tenant_id, operator_actor(credential)
        async with self.storage.write():
            row = await self.by_action(tenant, action_id)
            if not row:
                raise HTTPException(404, "Action not found")
            if row["status"] != "proposed":
                return public_action(row)
            if await self.target(tenant, row["incident_id"], row["source_id"]) != (row["source_id"], row["collector_id"]):
                return public_action(await self.transition(row, actor, "failed", "policy_changed", POLICY_DENIED))
            await self.enqueue(row, "scale")
            return public_action(await self.transition(row, actor, "approved", "queued_scale"))

    async def rollback(self, credential, action_id):
        tenant = credential.tenant_id
        async with self.storage.write():
            row = await self.by_action(tenant, action_id)
            if not row:
                raise HTTPException(404, "Action not found")
            if row["status"] in {"rollback_pending", "rolled_back", "rollback_failed"}:
                return public_action(row)
            if row["status"] != "succeeded" or self.owners.get((tenant, row["source_id"])) != row["collector_id"]:
                raise HTTPException(409, "A successful configured demo action is required")
            await self.enqueue(row, "rollback")
            return public_action(await self.transition(row, operator_actor(credential), "rollback_pending", "queued_rollback"))

    async def commands(self, credential):
        tenant, collector = credential.tenant_id, credential.collector_id
        async with self.storage.write():
            rows = await self.db.execute_fetchall(
                """SELECT a.*, c.command_id, c.kind, c.dispatched
                   FROM demo_action AS a JOIN demo_command AS c USING (tenant_id,action_id)
                   WHERE a.tenant_id=? AND a.collector_id=? AND c.result IS NULL
                   AND ((c.kind='scale' AND a.status IN ('approved','executing'))
                     OR (c.kind='rollback' AND a.status='rollback_pending')) LIMIT 20""", (tenant, collector),
            )
            items = []
            for row in rows:
                source = row["source_id"]
                if source not in credential.demo_source_ids:
                    continue
                if row["status"] == "approved":
                    if await self.target(tenant, row["incident_id"], source) != (source, collector):
                        await self.transition(row, "policy", "failed", "policy_changed", POLICY_DENIED)
                        continue
                    await self.transition(row, collector, "executing", "dispatched")
                if not row["dispatched"]:
                    await self.db.execute(
                        "UPDATE demo_command SET dispatched=1 WHERE tenant_id=? AND command_id=?",
                        (tenant, row["command_id"]),
                    )
                    if row["kind"] == "rollback":
                        await self.audit(tenant, row["action_id"], collector, "rollback_pending",
                                         "rollback_pending", "dispatched_rollback")
                items.append(DemoCommand(command_id=row["command_id"], action_id=row["action_id"],
                                         tenant_id=tenant, collector_id=collector, target_source_id=source,
                                         kind=row["kind"], playbook=PLAYBOOK, factor=FACTOR, simulation=True))
            return {"items": items}

    async def complete(self, credential, command_id, result: CommandResult):
        tenant, collector = credential.tenant_id, credential.collector_id
        body = canonical_bytes(result)
        async with self.storage.write():
            row = await self.one(
                """SELECT a.*,c.kind,c.dispatched,c.result
                   FROM demo_command AS c JOIN demo_action AS a USING (tenant_id,action_id)
                   WHERE c.tenant_id=? AND c.command_id=? AND a.collector_id=?""", (tenant, command_id, collector),
            )
            if not row or row["source_id"] not in credential.demo_source_ids:
                raise HTTPException(404, "Command not found")
            if row["result"] is not None:
                if row["result"] != body:
                    raise HTTPException(409, "Command result conflicts with the recorded result")
                return public_action(row)
            rollback = row["kind"] == "rollback"
            expected = "rollback_pending" if rollback else "executing"
            if row["status"] != expected or not row["dispatched"]:
                raise HTTPException(409, "Command is not in progress")
            success = result.outcome == "succeeded"
            if success:
                await self.validate_success(row, result, rollback)
            status = ("rolled_back" if success else "rollback_failed") if rollback else result.outcome
            await self.db.execute(
                "UPDATE demo_command SET result=? WHERE tenant_id=? AND command_id=?", (body, tenant, command_id),
            )
            return public_action(await self.transition(row, collector, status, result.reason_code))

    async def validate_success(self, row, result, rollback):
        if rollback:
            scale = await self.one(
                "SELECT result FROM demo_command WHERE tenant_id=? AND action_id=? AND kind='scale'",
                (row["tenant_id"], row["action_id"]),
            )
            prior = CommandResult.model_validate_json(scale["result"])
            valid = (result.reason_code == "snapshot_restored" and result.before_capacity_mb == prior.after_capacity_mb
                     and result.after_capacity_mb == prior.before_capacity_mb)
        else:
            valid = result.reason_code == "applied" and result.after_capacity_mb == scaled_capacity(result.before_capacity_mb)
        if not valid:
            raise HTTPException(422, "Result does not match the approved simulation")

    async def audit_page(self, tenant, before, limit):
        async with self.storage.lock:
            rows = await self.db.execute_fetchall(
                """SELECT t.id AS audit_id,t.actor,t.previous_status,t.status,t.reason_code,t.policy_verdict,
                          t.occurred_at,a.action_id,a.incident_id,a.source_id AS target_source_id
                   FROM demo_audit AS t JOIN demo_action AS a USING (tenant_id,action_id)
                   WHERE t.tenant_id=? AND t.id<? ORDER BY t.id DESC LIMIT ?""", (tenant, before, limit + 1),
            )
        return {
            "items": [{**dict(row), "playbook": PLAYBOOK, "simulation": True} for row in rows[:limit]],
            "next_cursor": str(rows[limit - 1]["audit_id"]) if len(rows) > limit else None,
        }
