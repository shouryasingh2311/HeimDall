"""Store operator-observed first render receipts and summarize measured cohorts."""

from datetime import timedelta
from math import ceil
from typing import Annotated

from pydantic import Field, field_validator

from backend.shared.models import Identifier, StrictModel, UtcString, UuidString, parse_utc, utc_now, utc_text

SCHEMA = """
CREATE TABLE IF NOT EXISTS render_receipt (
    tenant_id TEXT NOT NULL, run_id TEXT NOT NULL, session_id TEXT NOT NULL,
    payload_uuid TEXT NOT NULL, rendered_at TEXT NOT NULL, received_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, run_id, session_id, payload_uuid),
    FOREIGN KEY (tenant_id, payload_uuid) REFERENCES metadata (tenant_id, payload_uuid)
);
CREATE INDEX IF NOT EXISTS render_by_payload ON render_receipt (tenant_id, payload_uuid, run_id);
CREATE INDEX IF NOT EXISTS metadata_receive_time ON metadata (tenant_id, received_at);
"""


class RenderReceipt(StrictModel):
    run_id: Identifier
    session_id: Identifier
    payload_uuid: UuidString
    rendered_at_utc: UtcString
    dom_commit_duration_ms: Annotated[float, Field(ge=0)] | None = None

    @field_validator("rendered_at_utc")
    @classmethod
    def validate_time(cls, value: str):
        parse_utc(value)
        return value


async def record(storage, tenant: str, receipt: RenderReceipt) -> bool | None:
    async with storage.write():
        rows = await storage.db.execute_fetchall(
            "SELECT 1 FROM metadata WHERE tenant_id=? AND payload_uuid=?", (tenant, receipt.payload_uuid),
        )
        if not rows:
            return None
        cursor = await storage.db.execute(
            """INSERT INTO render_receipt VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT (tenant_id, run_id, session_id, payload_uuid) DO NOTHING""",
            (tenant, receipt.run_id, receipt.session_id, receipt.payload_uuid,
             utc_text(parse_utc(receipt.rendered_at_utc)), utc_text(utc_now())),
        )
        return cursor.rowcount == 1


def cohort_summary(entries):
    valid = []
    skewed = 0
    for event, accepted, rendered, posted in entries:
        if rendered is None:
            continue
        event_time, accepted_time, rendered_time, posted_time = map(parse_utc, (event, accepted, rendered, posted))
        if rendered_time < max(event_time, accepted_time) or rendered_time > posted_time:
            skewed += 1
        else:
            valid.append((rendered_time - event_time).total_seconds() * 1000)
    valid.sort()
    return {
        "eligible": len(entries), "samples": len(valid), "clock_flagged": skewed,
        "missing": len(entries) - len(valid) - skewed,
        "p50_ms": round(valid[ceil(len(valid) * .5) - 1], 2) if valid else None,
        "p95_ms": round(valid[ceil(len(valid) * .95) - 1], 2) if valid else None,
    }


async def summary(storage, tenant: str, run_id: str, session_id: str | None):
    now = utc_now()
    since = utc_text(now - timedelta(minutes=5))
    async with storage.lock:
        rows = await storage.db.execute_fetchall(
            """SELECT event_time, m.received_at, rendered_at, r.received_at, analysis_status
               FROM metadata AS m LEFT JOIN render_receipt AS r ON r.rowid=(
                   SELECT rowid FROM render_receipt WHERE tenant_id=m.tenant_id
                   AND payload_uuid=m.payload_uuid AND run_id=?
                   AND (? IS NULL OR session_id=?)
                   ORDER BY received_at, rowid LIMIT 1
               ) WHERE m.tenant_id=? AND m.received_at>=?""", (run_id, session_id, session_id, tenant, since),
        )
        offline = await storage.db.execute_fetchall(
            """SELECT collector_id, observed_at, heartbeat_at FROM offline_observation
               WHERE tenant_id=? AND observed_at>=? ORDER BY observed_at DESC LIMIT 20""", (tenant, since),
        )
    live, replay = [], []
    for event, received, rendered, posted, status in rows:
        bucket = replay if status == "historical" or (parse_utc(received) - parse_utc(event)).total_seconds() >= 10 else live
        bucket.append((event, received, rendered, posted))
    return {
        "run_id": run_id, "session_id": session_id, "window_seconds": 300,
        "clock_uncertainty": "Browser and producer clocks are not independently synchronized.",
        "live": cohort_summary(live), "replay_or_delayed": cohort_summary(replay), "all": cohort_summary(live + replay),
        "alert_delay_ms": None,
        "offline": [{
            "collector_id": row["collector_id"], "observed_at_utc": row["observed_at"],
            "last_heartbeat_utc": row["heartbeat_at"],
            "delay_ms": round((parse_utc(row["observed_at"]) - parse_utc(row["heartbeat_at"])).total_seconds() * 1000, 2),
        } for row in offline],
    }
