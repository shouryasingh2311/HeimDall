"""Count fresh authentication failures locally and queue only a typed summary."""

import asyncio
from datetime import datetime, timedelta
from hashlib import sha256
from hmac import digest
from ipaddress import IPv6Address, ip_address

from backend.collector.demo_source import RawEvent
from backend.collector.sanitizer import Sanitizer
from backend.shared.models import MetadataPayload, canonical_bytes, parse_utc, utc_text

SCHEMA = """
CREATE TABLE IF NOT EXISTS auth_failure (
    input_key TEXT PRIMARY KEY, source_id TEXT NOT NULL, attacker TEXT NOT NULL, event_time TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS auth_failure_window ON auth_failure (source_id, attacker, event_time);
CREATE INDEX IF NOT EXISTS auth_failure_expiry ON auth_failure (event_time);
"""


class QueueFull(Exception):
    pass


class SecurityAnalyzer:
    def __init__(self, db, capacity: int, sanitizer: Sanitizer):
        self.db = db
        self.capacity = capacity
        self.sanitizer = sanitizer
        self.key = bytes.fromhex(sanitizer.settings.hmac_key.get_secret_value())
        self.lock = asyncio.Lock()

    def fingerprint(self, domain: str, value: str) -> str:
        return digest(self.key, f"{domain}\0{value}".encode(), sha256).hex()

    async def submit(self, event: RawEvent, now: datetime) -> tuple[MetadataPayload, bytes] | None:
        source = self.sanitizer.source(event)
        if event.auth_success is True:
            return None
        if event.auth_success is not False or not isinstance(event.source_ip, str):
            raise ValueError("Invalid local authentication outcome or origin")
        address = ip_address(event.source_ip)
        if isinstance(address, IPv6Address):
            if address.scope_id is not None:
                raise ValueError("Unexpected address scope")
            address = address.ipv4_mapped or address
        attacker = "att-" + self.fingerprint("attacker", str(address))[:32]
        identity = self.fingerprint(source, event.input_id)
        if not event.event_time_utc.endswith("Z"):
            raise ValueError("Authentication timestamp must be UTC")
        event_time = parse_utc(event.event_time_utc)
        if event_time.utcoffset() != timedelta(0):
            raise ValueError("Authentication timestamp must be UTC")
        age = (now - event_time).total_seconds()
        if not -5 <= age < 30:
            return None
        start = utc_text(event_time - timedelta(seconds=10))
        timestamp = utc_text(event_time)
        async with self.lock:
            return await self.record(event, source, attacker, identity, start, timestamp, now)

    async def record(self, event, source, attacker, identity, start, timestamp, now):
        try:
            # This connection is reserved for authentication writes. The normal outbox
            # reader and drainer use a separate connection to the same database.
            await self.db.execute("BEGIN IMMEDIATE")
            await self.db.execute("DELETE FROM auth_failure WHERE event_time < ?", (
                utc_text(now - timedelta(seconds=45)),
            ))
            newer = await self.db.execute_fetchall(
                "SELECT 1 FROM auth_failure WHERE source_id=? AND attacker=? AND event_time>? LIMIT 1",
                (source, attacker, timestamp),
            )
            payload = None
            if not newer:
                cursor = await self.db.execute(
                    "INSERT OR IGNORE INTO auth_failure VALUES (?, ?, ?, ?)",
                    (identity, source, attacker, timestamp),
                )
                if cursor.rowcount == 1:
                    payload = await self.queue_summary(event, source, attacker, start, timestamp)
            await self.db.commit()
            return payload
        except BaseException:
            await self.db.rollback()
            raise

    async def queue_summary(self, event, source, attacker, start, timestamp):
        rows = await self.db.execute_fetchall(
            "SELECT count(*) FROM auth_failure WHERE source_id=? AND attacker=? AND event_time BETWEEN ? AND ?",
            (source, attacker, start, timestamp),
        )
        count = rows[0][0]
        if count < 5:
            return None
        payload = self.sanitizer.threat(event, attacker, count)
        body = canonical_bytes(payload)
        cursor = await self.db.execute(
            """INSERT INTO outbox (payload_uuid, body)
               SELECT ?, ? WHERE (SELECT count(*) FROM outbox) < ?
               ON CONFLICT (payload_uuid, body) DO NOTHING""",
            (payload.payload_uuid, body, self.capacity),
        )
        if not cursor.rowcount:
            existing = await self.db.execute_fetchall(
                "SELECT 1 FROM outbox WHERE payload_uuid=? AND body=?", (payload.payload_uuid, body),
            )
            if existing:
                return None
            raise QueueFull()
        return payload, body
