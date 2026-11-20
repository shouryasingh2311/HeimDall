"""Durable local outbox for approved wire bodies only."""

from contextlib import asynccontextmanager
from pathlib import Path
from time import time

import aiosqlite

from backend.shared.models import MetadataPayload

SCHEMA = """
CREATE TABLE IF NOT EXISTS outbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    payload_uuid TEXT NOT NULL,
    body BLOB NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    retry_at REAL NOT NULL DEFAULT 0,
    quarantine_reason TEXT,
    UNIQUE (payload_uuid, body)
);
CREATE INDEX IF NOT EXISTS outbox_ready ON outbox (retry_at, id)
WHERE quarantine_reason IS NULL;
"""


class Outbox:
    def __init__(self, db: aiosqlite.Connection, capacity: int):
        self.db = db
        self.capacity = capacity

    @classmethod
    @asynccontextmanager
    async def open(cls, path: Path, capacity: int):
        # Autocommit makes each single-statement transition atomic.
        async with aiosqlite.connect(path, isolation_level=None) as db:
            db.row_factory = aiosqlite.Row
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA synchronous=FULL")
            await db.executescript(SCHEMA)
            yield cls(db, capacity)

    async def enqueue(self, payload: MetadataPayload, body: bytes) -> str | None:
        key = (payload.payload_uuid, body)
        rows = await self.db.execute_fetchall(
            """INSERT INTO outbox (payload_uuid, body)
               SELECT ?, ? WHERE (SELECT count(*) FROM outbox) < ?
               ON CONFLICT (payload_uuid, body) DO NOTHING RETURNING quarantine_reason""",
            (*key, self.capacity),
        )
        if not rows:
            rows = await self.db.execute_fetchall(
                "SELECT quarantine_reason FROM outbox WHERE payload_uuid=? AND body=?", key,
            )
        if rows:
            return "quarantined" if rows[0]["quarantine_reason"] else "queued"
        return None

    async def next_ready(self):
        rows = await self.db.execute_fetchall(
            """SELECT * FROM outbox WHERE quarantine_reason IS NULL AND retry_at <= ?
               ORDER BY id LIMIT 1""", (time(),),
        )
        return rows[0] if rows else None

    async def retry(self, row_id: int, delay: float):
        await self.db.execute(
            "UPDATE outbox SET attempts=attempts+1, retry_at=? WHERE id=?", (time() + delay, row_id),
        )

    async def quarantine(self, row_id: int, reason: str):
        await self.db.execute(
            "UPDATE outbox SET attempts=attempts+1, quarantine_reason=? WHERE id=?", (reason, row_id),
        )

    async def acknowledge(self, row_id: int):
        await self.db.execute("DELETE FROM outbox WHERE id=?", (row_id,))

    async def counts(self) -> tuple[int, int]:
        rows = await self.db.execute_fetchall(
            "SELECT count(*) AS total, count(quarantine_reason) AS quarantined FROM outbox",
        )
        row = rows[0]
        return row["total"] - row["quarantined"], row["quarantined"]

    async def quarantined(self):
        rows = await self.db.execute_fetchall(
            """SELECT payload_uuid, quarantine_reason, attempts FROM outbox
               WHERE quarantine_reason IS NOT NULL ORDER BY id DESC LIMIT 20""",
        )
        return [dict(row) for row in rows]
