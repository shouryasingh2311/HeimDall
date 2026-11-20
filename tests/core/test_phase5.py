"""Live collector and SaaS controls for anomaly evidence and privacy."""

import asyncio
from dataclasses import replace
from datetime import timedelta
import json
import os
import sqlite3

import pytest

from backend.collector.buffer_queue import Outbox
from backend.collector.sanitizer import Sanitizer
from backend.collector.security_analyzer import QueueFull, SecurityAnalyzer
from backend.saas.incidents import IncidentEngine
from backend.saas.storage import Storage
from backend.shared.config import ServerSettings, read_settings
from backend.shared.models import canonical_bytes, utc_now, utc_text
from test_phase1 import collector_headers, operator, process, sample, service, settings


def incident_list(client, auth, **params):
    response = client.get("/api/v1/incidents", headers=auth, params=params)
    response.raise_for_status()
    return response.json()


def test_local_auth_window_privacy_replay_and_restart(service, tmp_path):
    runtime, client, _, _ = service
    config = settings(runtime, "alpha")
    viewer = operator(runtime, "alpha")
    base = utc_now() - timedelta(seconds=18)

    def failure(name, offset, address="198.51.100.8", **changes):
        return replace(
            sample(config, name, utc_text(base + timedelta(seconds=offset))),
            kind="auth", metrics=None, source_ip=address, auth_success=False,
            username="synthetic-user", raw_text="password=synthetic-private-value",
            **changes,
        )

    burst = [failure(f"burst-{i}", 8 + i) for i in range(5)]
    # Five attempts across 12 seconds never put five inside one 10-second window.
    spaced = [failure(f"spaced-{i}", 3 * i, "198.51.100.9") for i in range(5)]

    def replay(filename, events):
        source = tmp_path / filename
        source.write_text("".join(json.dumps(event.to_dict()) + "\n" for event in events), encoding="utf-8")
        with process("backend.collector.daemon", "--runtime", runtime, "--input", source, "--once") as proc:
            assert proc.wait(timeout=20) == 0

    replay("first.jsonl", [*spaced, *burst[:4], burst[1]])
    assert incident_list(client, viewer)["items"] == []
    replay("second.jsonl", [*burst, burst[-1]])
    items = incident_list(client, viewer)["items"]
    assert len(items) == 1 and items[0]["template_title"] == "Repeated failed logins"
    detail = client.get(f"/api/v1/incidents/{items[0]['incident_id']}", headers=viewer).json()
    signal, = detail["contributing_signals"]
    assert signal["observed"] == 5
    payload = client.get(f"/api/v1/payloads/{signal['payload_uuid']}", headers=viewer).json()
    assert payload["security"]["failed_attempts_count"] == 5
    assert payload["security"]["risk_score"] == 90
    assert payload["security"]["attacker_id"].startswith("att-")
    with sqlite3.connect(runtime / "saas.sqlite") as db:
        bodies = db.execute("SELECT body FROM metadata").fetchall()
    assert len(bodies) == 1
    for marker in (b"198.51.100.", b"synthetic-user", b"synthetic-private-value", b"source_ip", b"raw_text"):
        assert marker not in bodies[0][0]
    print("Auth control: no alerts for four failures or five spaced failures, one summary for five within the window.")


def test_statistical_control_and_related_unrelated_incidents(service):
    runtime, client, _, _ = service
    config = settings(runtime, "alpha")
    viewer = operator(runtime, "alpha")
    collector = collector_headers(config)
    sanitizer = Sanitizer(config)
    base = utc_now() - timedelta(seconds=13)
    endpoint = f"/api/v1/ingest/{config.region}"
    sequence = 0

    def ingest(node, offset, **metrics):
        nonlocal sequence
        sequence += 1
        raw = replace(sample(config, str(sequence), utc_text(base + timedelta(seconds=offset))),
                      source_key=f"{config.tenant_id}:{node}", metrics=metrics)
        payload = sanitizer.metric(raw)
        result = client.post(endpoint, content=canonical_bytes(payload), headers=collector)
        result.raise_for_status()
        return payload, result.json()

    for step in range(12):
        _, receipt = ingest("worker-01", step / 10, cpu_pct=20.)
        assert receipt["analysis_status"] == ("warming_up" if step < 10 else "live")
    ingest("worker-01", 2, cpu_pct=24.)
    ingest("worker-01", 3, cpu_pct=20.)
    assert incident_list(client, viewer)["items"] == []
    ingest("worker-01", 4, cpu_pct=26.)
    control_alert, _ = ingest("worker-01", 5, cpu_pct=27.)
    ingest("api-01", 6, latency_ms=550.)
    loss, _ = ingest("lb-01", 7, packet_loss_pct=12.)
    duplicate = client.post(endpoint, content=canonical_bytes(loss), headers=collector)
    assert duplicate.json()["status"] == "duplicate"
    _, older = ingest("lb-01", 6.5, packet_loss_pct=30.)
    assert older["analysis_status"] == "historical"

    results = incident_list(client, viewer)
    assert len(results["items"]) == 2
    correlated, unrelated = results["items"]
    assert correlated["evidence_score"] == 100 and unrelated["evidence_score"] == 30
    evidence_url = f"/api/v1/incidents/{correlated['incident_id']}"
    detail = client.get(evidence_url, headers=viewer).json()
    assert len(detail["alert_ids"]) == 2
    assert "may have contributed" in detail["likely_cause"]
    assert detail["reasoning_steps"][1].endswith("dependency=1, temporal order=1.")
    assert {signal["metric"] for signal in detail["contributing_signals"]} == {"latency_ms", "packet_loss_pct"}
    unrelated_url = f"/api/v1/incidents/{unrelated['incident_id']}"
    warning = client.get(unrelated_url, headers=viewer).json()
    point, = warning["contributing_signals"]
    assert point["payload_uuid"] == control_alert.payload_uuid
    assert (point["baseline_mean"], point["baseline_std"], point["z_score"]) == (20., 1., 7.)
    assert client.get(evidence_url, headers=operator(runtime, "beta")).status_code == 404
    assert client.get(evidence_url, headers=collector).status_code == 403
    assert incident_list(client, operator(runtime, "beta"))["items"] == []
    page = incident_list(client, viewer, limit=1)
    assert page["items"] == [correlated]
    assert incident_list(client, viewer, limit=1, cursor=page["next_cursor"])["items"] == [unrelated]

    timing = client.get("/api/v1/benchmarks", headers=viewer).json()
    assert timing["alert_timing"] == {"samples": 3, "clock_flagged": 0}
    assert timing["alert_delay_ms"] > 0
    print("Live ingest: 0/12 normal control alerts, 1 statistical warning, 2 related alerts in 1 incident.")

    for step in range(5):
        ingest("api-01", 8 + step / 10, latency_ms=20.)
    assert client.get(evidence_url, headers=viewer).json()["status"] == "recovering"
    for step in range(4):
        ingest("lb-01", 9 + step / 10, packet_loss_pct=0.)
    assert client.get(evidence_url, headers=viewer).json()["status"] == "recovering"
    ingest("lb-01", 10, packet_loss_pct=0.)
    assert client.get(evidence_url, headers=viewer).json()["status"] == "resolved"

    if os.getenv("HEIMDAL_TEST_DASHBOARD"):
        verify_incident_dashboard(client, viewer, loss.payload_uuid)


def test_live_breach_to_persisted_alert_timing(service):
    runtime, client, _, _ = service
    config = settings(runtime, "alpha")
    payload = Sanitizer(config).metric(replace(
        sample(config, "live-breach"), metrics={"packet_loss_pct": 12.},
    ))
    result = client.post(f"/api/v1/ingest/{config.region}", content=canonical_bytes(payload),
                         headers=collector_headers(config))
    assert result.json()["analysis_status"] == "live"
    benchmark = client.get("/api/v1/benchmarks", headers=operator(runtime, "alpha")).json()
    assert benchmark["alert_timing"] == {"samples": 1, "clock_flagged": 0}
    assert 0 < benchmark["alert_delay_ms"] <= 15000
    print(f"Injection to persisted packet-loss alert: {benchmark['alert_delay_ms']:.2f} ms.")


def test_auth_backpressure_rolls_back_the_triggering_failure(service, tmp_path):
    runtime, _, _, _ = service
    config = settings(runtime, "alpha")
    sanitizer = Sanitizer(config)
    now = utc_now()

    async def exercise():
        async with Outbox.open(tmp_path / "single-slot.sqlite", 1) as outbox:
            pending = sanitizer.metric(sample(config, "occupies-outbox"))
            await outbox.enqueue(pending, canonical_bytes(pending))
            analyzer = SecurityAnalyzer(outbox.security_db, outbox.capacity, sanitizer)
            for n in range(4):
                event = replace(sample(config, f"cap-{n}", utc_text(now)), kind="auth",
                                source_ip="198.51.100.30", auth_success=False)
                assert await analyzer.submit(event, now) is None
            fifth = replace(event, input_id="cap-4")
            with pytest.raises(QueueFull):
                await analyzer.submit(fifth, now)
            assert (await outbox.counts()) == (1, 0)
            row = await outbox.next_ready()
            await outbox.acknowledge(row["id"])
            payload, body = await analyzer.submit(fifth, now)
            assert payload.security.failed_attempts_count == 5
            assert (await outbox.next_ready())["body"] == body

    asyncio.run(exercise())


def test_baseline_and_incident_side_effects_commit_atomically_after_restart(service, tmp_path):
    runtime, _, _, _ = service
    config = settings(runtime, "alpha")
    server = read_settings(runtime / "saas.json", ServerSettings)
    sanitizer = Sanitizer(config)
    base = utc_now() - timedelta(seconds=5)
    path = tmp_path / "rollback.sqlite"

    def payload(step, value):
        source = sample(config, f"transaction-{step}", utc_text(base + timedelta(milliseconds=step * 100)))
        return sanitizer.metric(replace(source, metrics={"cpu_pct": value}))

    async def exercise():
        first_candidate = payload(10, 27.)
        breach = payload(11, 28.)
        async with Storage.open(path) as storage:
            engine = IncidentEngine(storage, server)
            storage.analyze = engine.analyze_locked
            for step in range(10):
                normal = payload(step, 20.)
                await storage.ingest(normal, canonical_bytes(normal))
            await storage.ingest(first_candidate, canonical_bytes(first_candidate))

            async def abort_after_analysis(_tenant):
                raise RuntimeError("Simulated failure before commit")

            storage.on_change = abort_after_analysis
            with pytest.raises(RuntimeError, match="before commit"):
                await storage.ingest(breach, canonical_bytes(breach))
            assert await storage.payload(config.tenant_id, breach.payload_uuid) is None
            assert (await engine.list(config.tenant_id, 2**63 - 1, 20))["items"] == []

        async with Storage.open(path) as storage:
            engine = IncidentEngine(storage, server)
            storage.analyze = engine.analyze_locked
            assert (await storage.ingest(breach, canonical_bytes(breach))).status == "accepted"
            assert (await storage.ingest(breach, canonical_bytes(breach))).status == "duplicate"
            items = (await engine.list(config.tenant_id, 2**63 - 1, 20))["items"]
            detail = await engine.detail(config.tenant_id, items[0]["incident_id"])
            assert len(items) == len(detail["alert_ids"]) == 1
            signal, = detail["contributing_signals"]
            assert (signal["baseline_mean"], signal["z_score"]) == (20., 8.)

    asyncio.run(exercise())


def verify_incident_dashboard(client, viewer, uuid):
    from playwright.sync_api import expect, sync_playwright

    origin = str(client.base_url).rstrip("/")
    with sync_playwright() as playwright, playwright.chromium.launch(channel=os.getenv("HEIMDAL_TEST_BROWSER")) as browser:
        page = browser.new_page()

        def forward(route):
            request = route.request
            headers = {k: v for k, v in request.all_headers().items() if k in {
                "authorization", "x-tenant-id", "content-type",
            }}
            response = client.request(request.method, request.url.removeprefix(origin), headers=headers,
                                      content=request.post_data_buffer)
            route.fulfill(status=response.status_code, body=response.content,
                          content_type=response.headers.get("content-type", "application/octet-stream"))

        page.route(f"{origin}/**", forward)
        page.goto(origin)
        page.get_by_label("Tenant ID").fill(viewer["X-Tenant-ID"])
        page.get_by_label("Operator token").fill(viewer["Authorization"].split()[1])
        page.get_by_role("button", name="Connect dashboard").click()
        page.get_by_role("tab", name="AIOps Incidents & Remediation").click()
        expect(page.get_by_text("may have contributed", exact=False)).to_be_visible()
        expect(page.get_by_text(uuid[:8], exact=False)).to_have_count(1)
