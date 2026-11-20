"""Serialized SQLite persistence for metadata and collector heartbeats."""

import asyncio
from contextlib import asynccontextmanager
from datetime import timedelta
import hashlib
from pathlib import Path

import aiosqlite

from backend.shared.models import (
    CollectorHeartbeat, IngestReceipt, MetadataPayload, PayloadDetail, canonical_bytes,
    parse_utc, utc_now, utc_text,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS metadata (
    tenant_id TEXT NOT NULL,
    payload_uuid TEXT NOT NULL,
    source_id TEXT NOT NULL,
    event_time TEXT NOT NULL,
    received_at TEXT NOT NULL,
    body_sha256 TEXT NOT NULL,
    body BLOB NOT NULL,
    event_type TEXT NOT NULL,
    analysis_status TEXT NOT NULL,
    PRIMARY KEY (tenant_id, payload_uuid)
);
CREATE INDEX IF NOT EXISTS metadata_source_time
ON metadata (tenant_id, source_id, event_type, event_time, payload_uuid);
CREATE TABLE IF NOT EXISTS heartbeat (
    tenant_id TEXT NOT NULL,
    collector_id TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    received_at TEXT NOT NULL,
    body BLOB NOT NULL,
    PRIMARY KEY (tenant_id, collector_id)
);
CREATE TABLE IF NOT EXISTS heartbeat_seen (
    tenant_id TEXT NOT NULL,
    collector_id TEXT NOT NULL,
    heartbeat_uuid TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, collector_id, heartbeat_uuid)
);
CREATE INDEX IF NOT EXISTS heartbeat_expiry ON heartbeat_seen (expires_at);
"""


class PayloadConflict(Exception):
    pass


class Storage:
    def __init__(self, db: aiosqlite.Connection):
        self.db = db
        self.lock = asyncio.Lock()

    @classmethod
    @asynccontextmanager
    async def open(cls, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(path) as db:
            db.row_factory = aiosqlite.Row
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA synchronous=FULL")
            await db.execute("PRAGMA foreign_keys=ON")
            await db.executescript(SCHEMA)
            yield cls(db)

    @asynccontextmanager
    async def write(self):
        async with self.lock:
            await self.db.execute("BEGIN IMMEDIATE")
            try:
                yield
                await self.db.commit()
            except BaseException:
                await self.db.rollback()
                raise

    async def ingest(self, payload: MetadataPayload, wire: bytes) -> IngestReceipt:
        digest = hashlib.sha256(wire).hexdigest()
        event_time = utc_text(parse_utc(payload.event_time_utc))
        now = utc_now()
        received_at = utc_text(now)
        async with self.write():
            identity = (payload.tenant_id, payload.payload_uuid)
            rows = await self.db.execute_fetchall(
                "SELECT * FROM metadata WHERE tenant_id=? AND payload_uuid=?", identity
            )
            if rows:
                row = rows[0]
                if row["body_sha256"] != digest:
                    raise PayloadConflict()
                return IngestReceipt(
                    payload_uuid=payload.payload_uuid, status="duplicate",
                    body_sha256=digest, received_at_utc=row["received_at"],
                    analysis_status=row["analysis_status"],
                )
            latest = await self.db.execute_fetchall(
                "SELECT max(event_time) AS latest FROM metadata WHERE tenant_id=? AND source_id=?",
                (payload.tenant_id, payload.source_id),
            )
            newest = latest[0]["latest"]
            analysis_status = (
                "historical"
                if (newest is not None and event_time <= newest)
                or now - parse_utc(payload.event_time_utc) >= timedelta(seconds=30)
                else "warming_up"
            )
            await self.db.execute(
                """INSERT INTO metadata
                   (tenant_id,payload_uuid,source_id,event_time,received_at,body_sha256,body,event_type,analysis_status)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (*identity, payload.source_id, event_time, received_at, digest,
                 canonical_bytes(payload), payload.event_type, analysis_status),
            )
            return IngestReceipt(
                payload_uuid=payload.payload_uuid, status="accepted", body_sha256=digest,
                received_at_utc=received_at, analysis_status=analysis_status,
            )

    async def heartbeat(self, beat: CollectorHeartbeat) -> bool:
        now = utc_text(utc_now())
        generated = utc_text(parse_utc(beat.generated_at_utc))
        async with self.write():
            await self.db.execute("DELETE FROM heartbeat_seen WHERE expires_at<?", (now,))
            cursor = await self.db.execute(
                "INSERT OR IGNORE INTO heartbeat_seen VALUES (?,?,?,?)",
                (beat.tenant_id, beat.collector_id, beat.heartbeat_uuid,
                 utc_text(parse_utc(generated) + timedelta(seconds=15))),
            )
            if cursor.rowcount == 0:
                return False
            cursor = await self.db.execute(
                """INSERT INTO heartbeat VALUES (?,?,?,?,?)
                   ON CONFLICT (tenant_id, collector_id) DO UPDATE SET
                       generated_at=excluded.generated_at, received_at=excluded.received_at, body=excluded.body
                   WHERE excluded.generated_at > heartbeat.generated_at""",
                (beat.tenant_id, beat.collector_id, generated, now, canonical_bytes(beat)),
            )
            return cursor.rowcount == 1

    @staticmethod
    def detail(row: aiosqlite.Row) -> PayloadDetail:
        payload = MetadataPayload.model_validate_json(row["body"])
        return PayloadDetail(
            **payload.model_dump(), body_sha256=row["body_sha256"],
            received_at_utc=row["received_at"], analysis_status=row["analysis_status"],
        )

    async def payload(self, tenant: str, uuid: str) -> PayloadDetail | None:
        async with self.lock:
            rows = await self.db.execute_fetchall(
                "SELECT * FROM metadata WHERE tenant_id=? AND payload_uuid=?", (tenant, uuid)
            )
        return self.detail(rows[0]) if rows else None

    async def metrics(self, tenant: str, source: str, after: tuple[str, str], limit: int):
        async with self.lock:
            return await self.db.execute_fetchall(
                """SELECT * FROM metadata WHERE tenant_id=? AND source_id=? AND event_type='metric'
                   AND (event_time, payload_uuid) > (?,?) ORDER BY event_time, payload_uuid LIMIT ?""",
                (tenant, source, *after, limit),
            )

    async def fleet(self, tenant: str):
        async with self.lock:
            beats = await self.db.execute_fetchall(
                "SELECT * FROM heartbeat WHERE tenant_id=? ORDER BY collector_id", (tenant,)
            )
            metrics = await self.db.execute_fetchall(
                """SELECT * FROM metadata AS point WHERE tenant_id=? AND event_type='metric'
                   AND payload_uuid=(SELECT payload_uuid FROM metadata
                       WHERE tenant_id=point.tenant_id AND source_id=point.source_id AND event_type='metric'
                       ORDER BY event_time DESC, payload_uuid DESC LIMIT 1)
                   ORDER BY source_id""",
                (tenant,),
            )
        return beats, metrics
