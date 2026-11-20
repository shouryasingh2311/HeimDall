"""Execute only the fixed memory playbook on the local DemoSource."""

import asyncio
from contextlib import asynccontextmanager
import logging
from pathlib import Path

import aiosqlite

from backend.collector.demo_source import DemoSource
from backend.collector.sanitizer import pseudonym
from backend.collector.transport import DELIVERY_ERRORS, Transport
from backend.shared.config import CollectorSettings
from backend.shared.models import canonical_bytes
from backend.shared.remediation import MAX_CAPACITY, CommandResult, DemoCommand, scaled_capacity

LOG = logging.getLogger("heimdal.collector")
NODE = "api-01"
SCHEMA = """
CREATE TABLE IF NOT EXISTS capacity (source_id TEXT PRIMARY KEY, capacity_mb INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS snapshot (
    action_id TEXT PRIMARY KEY, source_id TEXT NOT NULL, original_mb INTEGER NOT NULL,
    applied_mb INTEGER NOT NULL, restored INTEGER NOT NULL DEFAULT 0
);
CREATE UNIQUE INDEX IF NOT EXISTS active_snapshot ON snapshot (source_id) WHERE restored=0;
CREATE TABLE IF NOT EXISTS command_receipt (
    command_id TEXT PRIMARY KEY, action_id TEXT NOT NULL, kind TEXT NOT NULL, body BLOB NOT NULL,
    result BLOB NOT NULL, UNIQUE (action_id,kind)
);
"""


class CommandMismatch(Exception):
    pass


class CommandRunner:
    def __init__(self, db, config: CollectorSettings, source: DemoSource):
        if config.demo_memory_source != f"{config.tenant_id}:{NODE}":
            raise ValueError("A configured demo memory source is required")
        self.db = db
        self.config = config
        self.source = source
        self.target = pseudonym(config.hmac_key.get_secret_value(), config.demo_memory_source)
        self.lock = asyncio.Lock()

    @classmethod
    @asynccontextmanager
    async def open(cls, path: Path, config: CollectorSettings, source: DemoSource):
        async with aiosqlite.connect(path) as db:
            db.row_factory = aiosqlite.Row
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA synchronous=FULL")
            await db.executescript(SCHEMA)
            runner = cls(db, config, source)
            source.scale_container_memory(NODE, await runner.capacity())
            yield runner

    async def one(self, query, params):
        rows = await self.db.execute_fetchall(query, params)
        return rows[0] if rows else None

    async def capacity(self):
        row = await self.one("SELECT capacity_mb FROM capacity WHERE source_id=?", (self.target,))
        return row[0] if row else self.source.memory_capacities[NODE]

    async def execute(self, command: DemoCommand) -> CommandResult:
        if (command.tenant_id, command.collector_id, command.target_source_id) != (
            self.config.tenant_id, self.config.collector_id, self.target,
        ):
            raise CommandMismatch("Command does not match configured demo scope")
        body = canonical_bytes(command)
        async with self.lock:
            try:
                await self.db.execute("BEGIN IMMEDIATE")
                receipt = await self.one(
                    """SELECT body,result FROM command_receipt WHERE command_id=?
                       OR (action_id=? AND kind=?)""", (command.command_id, command.action_id, command.kind),
                )
                if receipt:
                    if receipt["body"] != body:
                        raise CommandMismatch("Command conflicts with a local receipt")
                    await self.db.commit()
                    return CommandResult.model_validate_json(receipt["result"])
                result = await self.apply(command)
                await self.db.execute(
                    "INSERT INTO command_receipt VALUES (?,?,?,?,?)",
                    (command.command_id, command.action_id, command.kind, body, canonical_bytes(result)),
                )
                await self.db.commit()
            except BaseException:
                await self.db.rollback()
                raise
            if result.after_capacity_mb is not None:
                self.source.scale_container_memory(NODE, result.after_capacity_mb)
            return result

    async def apply(self, command):
        before = await self.capacity()
        if command.kind == "scale":
            active = await self.one("SELECT 1 FROM snapshot WHERE source_id=? AND restored=0", (self.target,))
            if active:
                return CommandResult(simulation=True, outcome="failed", reason_code="capacity_changed")
            after = scaled_capacity(before)
            if after <= before or after > MAX_CAPACITY:
                return CommandResult(simulation=True, outcome="failed", reason_code="capacity_limit")
            await self.db.execute(
                "INSERT INTO snapshot (action_id,source_id,original_mb,applied_mb) VALUES (?,?,?,?)",
                (command.action_id, self.target, before, after),
            )
            reason = "applied"
        else:
            snapshot = await self.one(
                "SELECT * FROM snapshot WHERE action_id=? AND source_id=?", (command.action_id, self.target),
            )
            if not snapshot:
                return CommandResult(simulation=True, outcome="failed", reason_code="snapshot_missing")
            if snapshot["restored"] or before != snapshot["applied_mb"]:
                return CommandResult(simulation=True, outcome="failed", reason_code="capacity_changed")
            after = snapshot["original_mb"]
            await self.db.execute("UPDATE snapshot SET restored=1 WHERE action_id=?", (command.action_id,))
            reason = "snapshot_restored"
        await self.db.execute(
            """INSERT INTO capacity VALUES (?,?) ON CONFLICT (source_id)
               DO UPDATE SET capacity_mb=excluded.capacity_mb""", (self.target, after),
        )
        return CommandResult(simulation=True, outcome="succeeded", reason_code=reason,
                             before_capacity_mb=before, after_capacity_mb=after)

    async def run(self, transport: Transport):
        while True:
            try:
                for command in await transport.commands():
                    result = await self.execute(command)
                    await transport.command_result(command.command_id, result)
            except (*DELIVERY_ERRORS, CommandMismatch) as error:
                LOG.warning("Demo command exchange failed (%s)", type(error).__name__)
            await asyncio.sleep(2)
