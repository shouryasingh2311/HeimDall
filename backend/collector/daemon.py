"""Read local events and deliver approved metadata using verified HTTPS."""

import argparse
import asyncio
from contextlib import asynccontextmanager
from dataclasses import replace
import logging
from pathlib import Path
from uuid import uuid4

import httpx
import psutil
from pydantic import ValidationError
import uvicorn

from backend.collector.adapters.jsonl_adapter import JSONLAdapter
from backend.collector.adapters.organizer_adapter import OrganizerAdapter
from backend.collector.demo_source import DemoSource, RawEvent
from backend.collector.inspector import AuditPreview, create_inspector
from backend.collector.sanitizer import Sanitizer
from backend.collector.transport import ReceiptMismatch, Transport
from backend.shared.config import CollectorSettings, read_settings
from backend.shared.models import CollectorHeartbeat, canonical_bytes, utc_now, utc_text

LOG = logging.getLogger("cicada.collector")
DELIVERY_ERRORS = (httpx.HTTPError, ReceiptMismatch, ValidationError)


class Collector:
    def __init__(self, settings: CollectorSettings, transport: Transport, audit: AuditPreview):
        self.settings = settings
        self.transport = transport
        self.audit = audit
        self.sanitizer = Sanitizer(settings)
        self.process = psutil.Process()
        self.process.cpu_percent()

    async def submit(self, event: RawEvent) -> bool:
        try:
            payload = self.sanitizer.metric(event)
        except ValueError:
            LOG.warning("Rejected local event with invalid identity or metrics")
            return False
        if payload is None:
            return True
        approved = canonical_bytes(payload)
        record = self.audit.add(event, payload, approved)
        record["state"] = "sending"
        try:
            receipt = await self.transport.send(payload, approved)
        except DELIVERY_ERRORS as error:
            record["state"] = "failed"
            LOG.warning("Delivery failed for approved payload %s (%s)", payload.payload_uuid, type(error).__name__)
            return False
        record["receipt"] = receipt.model_dump(mode="json")
        record["state"] = "acknowledged"
        return True

    async def heartbeat(self):
        config = self.settings
        beat = CollectorHeartbeat(
            schema_version=1, tenant_id=config.tenant_id, collector_id=config.collector_id,
            region=config.region, heartbeat_uuid=str(uuid4()), generated_at_utc=utc_text(utc_now()),
            source_timezone="UTC", version="0.1.0", rss_mb=self.process.memory_info().rss / (1024 * 1024),
            cpu_pct=min(100., self.process.cpu_percent() / (psutil.cpu_count() or 1)),
            queue_depth=0, config_status="valid",
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
            delivered = True
            count = 0
            async for event in adapter.events():
                count += 1
                delivered = await self.submit(event) and delivered
            if adapter.malformed_count or count == 0:
                LOG.error("Input produced %s records and %s malformed records", count, adapter.malformed_count)
                return False
            return delivered

        LOG.info("Input mode: DEMO_FALLBACK")
        generator = DemoSource()
        while True:
            delivered = True
            for event in generator.generate_tick(tenants=[self.settings.tenant_id]):
                event = replace(event, collector_id=self.settings.collector_id)
                delivered = await self.submit(event) and delivered
            if args.once:
                return delivered
            await asyncio.sleep(2)


async def run(args, settings: CollectorSettings) -> bool:
    audit = AuditPreview()
    async with Transport(settings, args.runtime / "ca.pem") as transport:
        collector = Collector(settings, transport, audit)
        if args.once:
            try:
                await collector.heartbeat()
            except DELIVERY_ERRORS as error:
                LOG.error("SaaS connection failed (%s)", type(error).__name__)
                return False
            return await collector.events(args)

        app = create_inspector(settings, audit)
        inspector_lifespan = app.router.lifespan_context

        @asynccontextmanager
        async def lifespan(app):
            async def read_events():
                try:
                    if not await collector.events(args):
                        LOG.error("Input run failed. See local collector diagnostics.")
                except (OSError, UnicodeError) as error:
                    LOG.error("Input could not be read (%s)", type(error).__name__)

            async with inspector_lifespan(app):
                tasks = [asyncio.create_task(collector.send_heartbeats()), asyncio.create_task(read_events())]
                try:
                    yield
                finally:
                    for task in tasks:
                        task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)

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
