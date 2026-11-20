"""Phase 3 checks using disk-backed queues and the real HTTPS API."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import sqlite3
import ssl
import time

import httpx

from backend.collector.buffer_queue import Outbox
from backend.collector.daemon import Collector
from backend.collector.inspector import AuditPreview
from backend.collector.sanitizer import Sanitizer
from backend.collector.transport import Transport
from backend.shared.models import canonical_bytes
from scripts.security.bootstrap import bootstrap
from test_phase1 import collector_headers, free_port, operator, process, sample, service, settings, wait_for


def wait_status(local, headers, predicate, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = local.get("/api/local/status", headers=headers).json()
        if predicate(status):
            return status
        time.sleep(0.1)
    raise AssertionError(f"Collector did not reach expected status: {status}")


def test_thirty_second_outage_recovers_exact_ids_after_restart(tmp_path):
    runtime, port, local_port = tmp_path / "runtime", free_port(), free_port()
    bootstrap(runtime, port, local_port)
    config = settings(runtime, "alpha")
    local_headers = {"Authorization": f"Bearer {config.local_token.get_secret_value()}"}
    tls = ssl.create_default_context(cafile=str(runtime / "ca.pem"))
    collector_args = ("backend.collector.daemon", "--runtime", runtime)
    server_args = ("backend.saas.main", "--runtime", runtime, "--port", port)
    with (
        httpx.Client(base_url=f"https://localhost:{port}", verify=tls, trust_env=False) as central,
        httpx.Client(base_url=f"http://127.0.0.1:{local_port}", trust_env=False) as local,
    ):
        with process(*server_args) as api:
            wait_for(central, "/healthz", api)
        with process(*collector_args) as proc:
            wait_for(local, "/api/local/status", proc, local_headers)
            first = wait_status(local, local_headers, lambda status: status["queue_depth"] > 0)
            time.sleep(30)
            later = local.get("/api/local/status", headers=local_headers).json()
            assert later["queue_depth"] > first["queue_depth"]
            assert later["session_receipts"] == {"accepted": 0, "duplicate": 0}

        with sqlite3.connect(next(runtime.glob("outbox-*.sqlite3"))) as db:
            queued = dict(db.execute("SELECT payload_uuid, body FROM outbox"))
        assert len(queued) >= later["queue_depth"]
        assert all(b"raw_text" not in body for body in queued.values())

        event = sample(config, "after-restart")
        payload = Sanitizer(config).metric(event)
        queued[payload.payload_uuid] = canonical_bytes(payload)
        source = tmp_path / "restart.jsonl"
        source.write_text(json.dumps(event.to_dict()) + "\n", encoding="utf-8")
        with process(*collector_args, "--input", source) as proc:
            wait_for(local, "/api/local/status", proc, local_headers)
            wait_status(local, local_headers, lambda status: status["queue_depth"] == len(queued))
            with process(*server_args) as api:
                wait_for(central, "/healthz", api)
                end = wait_status(local, local_headers, lambda status: (
                    status["queue_depth"] == 0 and status["session_receipts"]["accepted"] == len(queued)
                ))
                assert end["quarantine_count"] == 0
                assert end["session_receipts"] == {"accepted": len(queued), "duplicate": 0}
                with sqlite3.connect(runtime / "saas.sqlite") as db:
                    persisted = db.execute("SELECT payload_uuid, body FROM metadata").fetchall()
                assert len(persisted) == len(queued)
                assert dict(persisted) == queued


def test_lost_ack_retry_backpressure_and_conflict(service, tmp_path):
    runtime, central, _, _ = service
    config = settings(runtime, "alpha")
    path = tmp_path / "outbox.sqlite3"
    first = sample(config, "lost-ack")
    second = sample(config, "after-capacity")
    payload = Sanitizer(config).metric(first)
    wire = canonical_bytes(payload)

    async def exercise():
        async with Transport(config, runtime / "ca.pem") as transport:
            send = transport.send

            async def lose_ack(data, body):
                assert body == wire
                assert (await send(data, body)).status == "accepted"
                raise httpx.ReadTimeout("Simulated lost response after durable SaaS commit")

            async with Outbox.open(path, 1) as outbox:
                collector = Collector(config, transport, AuditPreview(), outbox)
                assert await collector.submit(first)
                blocked = asyncio.create_task(collector.submit(second))
                try:
                    async with asyncio.timeout(2):
                        while not collector.backpressure:
                            await asyncio.sleep(0.01)
                    assert (await collector.queue_status())["backpressure"]
                    assert not blocked.done()
                    transport.send = lose_ack
                    assert await collector.drainer.deliver_next()
                    assert await outbox.counts() == (1, 0)
                    assert collector.drainer.receipts == {"accepted": 0, "duplicate": 0}
                finally:
                    blocked.cancel()
                    await asyncio.gather(blocked, return_exceptions=True)

            transport.send = send
            async with Outbox.open(path, 1) as outbox:
                collector = Collector(config, transport, AuditPreview(), outbox)
                async with asyncio.timeout(3):
                    while not await collector.drainer.deliver_next():
                        await asyncio.sleep(0.05)
                assert collector.drainer.receipts == {"accepted": 0, "duplicate": 1}
                assert await outbox.counts() == (0, 0)
                changed = payload.model_copy(update={
                    "metrics": payload.metrics.model_copy(update={"cpu_pct": 99.0}),
                })
                assert await outbox.enqueue(changed, canonical_bytes(changed)) == "queued"
                assert await collector.drainer.deliver_next()
                status = await collector.queue_status()
                assert status["queue_depth"] == 0
                assert status["quarantine_items"] == [{
                    "payload_uuid": payload.payload_uuid, "quarantine_reason": "uuid_conflict", "attempts": 1,
                }]
                assert status["backpressure"]

    asyncio.run(exercise())
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT quarantine_reason FROM outbox").fetchall() == [("uuid_conflict",)]
    with sqlite3.connect(runtime / "saas.sqlite") as db:
        assert db.execute("SELECT payload_uuid, body FROM metadata").fetchall() == [(payload.payload_uuid, wire)]
    assert central.get(f"/api/v1/payloads/{payload.payload_uuid}", headers=operator(runtime, "alpha")).status_code == 200


def test_concurrent_identical_posts_commit_one_metadata_row(service):
    runtime, central, _, _ = service
    config = settings(runtime, "alpha")
    payload = Sanitizer(config).metric(sample(config, "concurrent-replay"))
    wire = canonical_bytes(payload)

    def post(_):
        response = central.post(f"/api/v1/ingest/{config.region}", content=wire, headers=collector_headers(config))
        response.raise_for_status()
        return response.json()

    with ThreadPoolExecutor(max_workers=8) as workers:
        receipts = list(workers.map(post, range(8)))
    assert sorted(receipt["status"] for receipt in receipts) == ["accepted"] + ["duplicate"] * 7
    assert len({receipt["received_at_utc"] for receipt in receipts}) == 1
    with sqlite3.connect(runtime / "saas.sqlite") as db:
        assert db.execute("SELECT payload_uuid, body FROM metadata").fetchall() == [(payload.payload_uuid, wire)]
