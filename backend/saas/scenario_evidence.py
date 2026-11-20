"""Persist safe scenario summaries and observe committed collector evidence."""

from datetime import timedelta
import json

from fastapi import HTTPException

from backend.shared.models import MetadataPayload, canonical_bytes, parse_utc, utc_now, utc_text
from backend.shared.scenarios import RESULT_GRACE_SECONDS, scenario_timeout

SCHEMA = """
CREATE TABLE IF NOT EXISTS scenario_result (
    tenant_id TEXT NOT NULL, collector_id TEXT NOT NULL, run_id TEXT NOT NULL, scenario_id INTEGER NOT NULL,
    status TEXT NOT NULL, started_at TEXT NOT NULL, result BLOB NOT NULL,
    PRIMARY KEY (tenant_id,run_id)
);
CREATE INDEX IF NOT EXISTS scenario_by_number ON scenario_result (tenant_id,scenario_id,started_at);
"""


async def save(storage, credential, result):
    if not credential.demo_source_ids:
        raise HTTPException(403, "A demo collector is required")
    if parse_utc(result.started_at_utc) > utc_now() + timedelta(seconds=5):
        raise HTTPException(422, "Scenario start is in the future")
    body = canonical_bytes(result)
    tenant, collector = credential.tenant_id, credential.collector_id
    async with storage.write():
        if result.status == "passed":
            owned = await storage.db.execute_fetchall(
                """SELECT payload_uuid FROM metadata WHERE tenant_id=?
                   AND payload_uuid IN (SELECT value FROM json_each(?))
                   AND source_id IN (SELECT value FROM json_each(?))""",
                (tenant, json.dumps(result.payload_uuids), json.dumps(credential.source_ids)),
            )
            if {row[0] for row in owned} != set(result.payload_uuids):
                raise HTTPException(422, "Passing evidence must reference committed payloads in scope")
        rows = await storage.db.execute_fetchall(
            "SELECT * FROM scenario_result WHERE tenant_id=? AND run_id=?", (tenant, result.run_id),
        )
        if rows:
            old = rows[0]
            if (old["collector_id"], old["scenario_id"], old["started_at"]) != (collector, result.scenario_id, result.started_at_utc):
                raise HTTPException(409, "Run identity conflict")
            if old["status"] != "running":
                if old["result"] != body:
                    raise HTTPException(409, "Run already finalized")
                return
            await storage.db.execute(
                "UPDATE scenario_result SET status=?,result=? WHERE tenant_id=? AND run_id=?",
                (result.status, body, tenant, result.run_id),
            )
        else:
            await storage.db.execute(
                "INSERT INTO scenario_result VALUES (?,?,?,?,?,?,?)",
                (tenant, collector, result.run_id, result.scenario_id, result.status, result.started_at_utc, body),
            )


async def latest(storage, tenant):
    async with storage.lock:
        rows = await storage.db.execute_fetchall(
            """SELECT result FROM (SELECT result,scenario_id,row_number() OVER
               (PARTITION BY scenario_id ORDER BY started_at DESC,run_id DESC) AS rank
               FROM scenario_result WHERE tenant_id=?) WHERE rank=1 ORDER BY scenario_id""", (tenant,),
        )
    now = utc_now()
    results = [json.loads(row[0]) for row in rows]
    for result in results:
        if result["status"] != "running":
            continue
        # Keep the stored run open for genuine evidence that arrives after reconnect.
        window = timedelta(seconds=scenario_timeout(result["scenario_id"]) + RESULT_GRACE_SECONDS)
        try:
            started = parse_utc(result["started_at_utc"])
        except ValueError:  # A runtime created before timestamp validation may contain invalid dates.
            deadline = now
        else:
            if started > now - window:
                continue
            deadline = started + window
        result.update(status="blocked", reason_code="result_not_reported", finished_at_utc=utc_text(deadline))
    return results


async def observe(storage, credential, ids):
    if not credential.demo_source_ids:
        raise HTTPException(403, "A demo collector is required")
    params = (credential.tenant_id, json.dumps(ids), json.dumps(credential.source_ids))
    async with storage.lock:
        rows = await storage.db.execute_fetchall(
            """SELECT body,payload_uuid,body_sha256,analysis_status FROM metadata WHERE tenant_id=?
               AND payload_uuid IN (SELECT value FROM json_each(?))
               AND source_id IN (SELECT value FROM json_each(?))""", params,
        )
        alerts = await storage.db.execute_fetchall(
            """SELECT payload_uuid,incident_id,metric,event_time,created_at FROM alert WHERE tenant_id=?
               AND payload_uuid IN (SELECT value FROM json_each(?))
               AND source_id IN (SELECT value FROM json_each(?))""", params,
        )
        actions = await storage.db.execute_fetchall(
            """SELECT a.incident_id,a.action_id,a.status FROM demo_action AS a
               WHERE a.tenant_id=? AND a.collector_id=? AND a.incident_id IN
               (SELECT incident_id FROM alert WHERE tenant_id=a.tenant_id
                AND payload_uuid IN (SELECT value FROM json_each(?)))""",
            (credential.tenant_id, credential.collector_id, json.dumps(ids)),
        )
        pending = await storage.db.execute_fetchall(
            """SELECT count(*) FROM demo_action WHERE tenant_id=? AND collector_id=?
               AND status IN ('proposed','approved','executing','succeeded','rollback_pending','rollback_failed')""",
            (credential.tenant_id, credential.collector_id),
        )
    return {
        "payloads": {row["payload_uuid"]: {
            "body": MetadataPayload.model_validate_json(row["body"]).model_dump(mode="json"),
            "body_sha256": row["body_sha256"], "analysis_status": row["analysis_status"],
        } for row in rows},
        "alerts": [dict(row) for row in alerts], "actions": [dict(row) for row in actions],
        "pending_actions": pending[0][0],
    }
