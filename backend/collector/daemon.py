"""Read local events and deliver approved metadata using verified HTTPS."""

import argparse
import asyncio
from contextlib import asynccontextmanager
from dataclasses import replace
from hashlib import sha256
import logging
from pathlib import Path
from uuid import uuid4

import psutil
import uvicorn

from backend.collector.adapters.jsonl_adapter import JSONLAdapter
from backend.collector.adapters.organizer_adapter import OrganizerAdapter
from backend.collector.buffer_queue import Outbox
from backend.collector.demo_source import DemoSource, RawEvent
from backend.collector.drainer import DELIVERY_ERRORS, Drainer
from backend.collector.inspector import AuditPreview, create_inspector
from backend.collector.sanitizer import Sanitizer
from backend.collector.security_analyzer import QueueFull, SecurityAnalyzer
from backend.collector.transport import Transport
from backend.shared.config import CollectorSettings, read_settings
from backend.shared.models import CollectorHeartbeat, canonical_bytes, utc_now, utc_text

LOG = logging.getLogger("cicada.collector")


class Collector:
    def __init__(self, settings: CollectorSettings, transport: Transport, audit: AuditPreview, outbox: Outbox):
        self.settings = settings
        self.transport = transport
        self.audit = audit
        self.outbox = outbox
        self.drainer = Drainer(outbox, transport, audit)
        self.backpressure = False
        self.sanitizer = Sanitizer(settings)
        self.security = SecurityAnalyzer(outbox.security_db, outbox.capacity, self.sanitizer)
        self.process = psutil.Process()
        self.process.cpu_percent()

    async def submit(self, event: RawEvent) -> bool:
        try:
            return await self.queue_event(event)
        except ValueError:
            LOG.warning("Rejected invalid local event")
            return False
        finally:
            self.backpressure = False

    async def queue_event(self, event: RawEvent) -> bool:
        if event.kind == "auth":
            observed_at = utc_now()
            while True:
                try:
                    summary = await self.security.submit(event, observed_at)
                    break
                except QueueFull:
                    await self.wait_for_capacity()
            if summary is not None:
                payload, body = summary
                self.audit.add(event, payload, body)["state"] = "queued"
            return True

        payload = self.sanitizer.metric(event)
        approved = canonical_bytes(payload)
        while (state := await self.outbox.enqueue(payload, approved)) is None:
            await self.wait_for_capacity()
        if self.audit.by_id(payload.payload_uuid, approved_body=approved.decode()) is None:
            self.audit.add(event, payload, approved)["state"] = state
        return state != "quarantined"

    async def wait_for_capacity(self):
        if not self.backpressure:
            LOG.warning("Outbox full; input is paused")
        self.backpressure = True
        await asyncio.sleep(0.25)

    async def queue_status(self):
        pending, quarantined = await self.outbox.counts()
        return {
            "buffering": "enabled", "queue_depth": pending, "capacity": self.outbox.capacity,
            "backpressure": self.backpressure or pending + quarantined >= self.outbox.capacity,
            "quarantine_count": quarantined, "quarantine_items": await self.outbox.quarantined(),
            "session_receipts": dict(self.drainer.receipts),
        }

    async def heartbeat(self):
        config = self.settings
        pending, _ = await self.outbox.counts()
        beat = CollectorHeartbeat(
            schema_version=1, tenant_id=config.tenant_id, collector_id=config.collector_id,
            region=config.region, heartbeat_uuid=str(uuid4()), generated_at_utc=utc_text(utc_now()),
            source_timezone="UTC", version="0.1.0", rss_mb=self.process.memory_info().rss / (1024 * 1024),
            cpu_pct=min(100., self.process.cpu_percent() / (psutil.cpu_count() or 1)),
            queue_depth=pending, config_status="valid",
        )
        await self.transport.heartbeat(beat)

    async def send_heartbeats(self):
        while True:
            try:
                await self.heartbeat()
            except DELIVERY_ERRORS as error:
                LOG.warning("Heartbeat failed (%s)", type(error).__name__)
            await asyncio.sleep(10)

    async def events(self, args):
        if args.input is not None or args.organizer is not None:
            path = args.input or args.organizer
            if not path.is_file():
                LOG.error("Explicit input file is missing")
                return False
            if args.input is not None:
                adapter = JSONLAdapter(path)
                LOG.info("Input mode: local JSONL")
            else:
                adapter = OrganizerAdapter(path, self.settings.tenant_id, self.settings.collector_id)
                LOG.info("Input mode: organizer adapter; stream compatibility depends on supplied input")
            accepted = True
            count = 0
            async for event in adapter.events():
                count += 1
                accepted = await self.submit(event) and accepted
            if adapter.malformed_count or count == 0:
                LOG.error("Input produced %s records and %s malformed records", count, adapter.malformed_count)
                return False
            return accepted

        LOG.info("Input mode: DEMO_FALLBACK")
        generator = DemoSource()
        while True:
            accepted = True
            for event in generator.generate_tick(tenants=[self.settings.tenant_id]):
                event = replace(event, collector_id=self.settings.collector_id)
                accepted = await self.submit(event) and accepted
            if args.once:
                return accepted
            await asyncio.sleep(2)


async def run(args, settings: CollectorSettings) -> bool:
    audit = AuditPreview()
    scope = sha256("\0".join((settings.tenant_id, settings.collector_id, settings.region)).encode()).hexdigest()
    outbox_path = args.runtime / f"outbox-{scope}.sqlite3"
    async with (
        Transport(settings, args.runtime / "ca.pem") as transport,
        Outbox.open(outbox_path, settings.outbox_capacity) as outbox,
    ):
        collector = Collector(settings, transport, audit, outbox)

        @asynccontextmanager
        async def workers(*jobs):
            async with asyncio.TaskGroup() as group:
                tasks = [group.create_task(job) for job in jobs]
                try:
                    yield
                finally:
                    for task in tasks:
                        task.cancel()

        if args.once:
            async with workers(collector.drainer.run(), collector.send_heartbeats()):
                try:
                    async with asyncio.timeout(20):
                        accepted = await collector.events(args)
                        while (await outbox.counts())[0]:
                            await asyncio.sleep(0.1)
                        return accepted and (await outbox.counts())[1] == 0
                except TimeoutError:
                    LOG.error("Timed out waiting for delivery; committed records remain in the outbox")
                    return False

        app = create_inspector(settings, audit, collector.queue_status)
        inspector_lifespan = app.router.lifespan_context

        @asynccontextmanager
        async def lifespan(app):
            async def read_events():
                try:
                    if not await collector.events(args):
                        LOG.error("Input run failed. See local collector diagnostics.")
                except (OSError, UnicodeError) as error:
                    LOG.error("Input could not be read (%s)", type(error).__name__)

            async with inspector_lifespan(app), workers(
                collector.drainer.run(), collector.send_heartbeats(), read_events(),
            ):
                yield

        app.router.lifespan_context = lifespan
        server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=settings.local_port, proxy_headers=False))
        await server.serve()
        return server.started


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, default=Path(".cicada/dev"))
    parser.add_argument("--tenant", choices=["alpha", "beta"], default="alpha")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--input", type=Path, help="Local RawEvent JSONL file")
    source.add_argument("--organizer", type=Path, help="Organizer JSONL file")
    parser.add_argument("--once", action="store_true", help="Send one batch or file and exit")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    settings = read_settings(args.runtime / f"collector-{args.tenant}.json", CollectorSettings)
    raise SystemExit(0 if asyncio.run(run(args, settings)) else 1)


if __name__ == "__main__":
    main()
