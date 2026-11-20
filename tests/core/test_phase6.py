"""Verify the demo-only policy, durable command delivery and real telemetry."""

import asyncio
from dataclasses import replace
from datetime import timedelta
import os
import time
from uuid import uuid4

import pytest

from backend.collector.command_runner import CommandMismatch, CommandRunner, NODE
from backend.collector.demo_source import DemoSource
from backend.collector.sanitizer import Sanitizer
from backend.shared.models import canonical_bytes, parse_utc, utc_now, utc_text
from backend.shared.remediation import DemoCommand
from test_phase1 import collector_headers, operator, process, sample, service, settings

COMMANDS = "/api/v1/collector/commands"
AUDIT = "/api/v1/remediation/audit"


def wait_until(read, timeout=18):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = read()
        if result:
            return result
        time.sleep(0.2)
    pytest.fail("Expected live simulation state was not observed")


def test_demo_approval_recovery_restart_and_rollback(service, tmp_path):
    runtime, client, _, _ = service
    config = settings(runtime, "alpha")
    viewer, edge = operator(runtime, "alpha"), collector_headers(config)
    launch = ("backend.collector.daemon", "--runtime", runtime, "--demo-memory-pressure")

    def incidents():
        return client.get("/api/v1/incidents", headers=viewer).json()["items"]

    with (tmp_path / "collector.log").open("w") as log:
        with process(*launch, stderr=log):
            incident, = wait_until(incidents)
        incident_path = f"/api/v1/incidents/{incident['incident_id']}"
        initial = client.get(incident_path, headers=viewer).json()
        assert initial["remediation_eligible"]
        initial_memory = next(signal["observed"] for signal in initial["contributing_signals"]
                              if signal["metric"] == "memory_pct")
        assert 95 < initial_memory <= 100
        proposal = incident_path + "/proposal"
        assert client.post(proposal, headers=edge).status_code == 403
        assert client.post(proposal, headers=operator(runtime, "beta")).status_code == 404
        assert client.post(proposal, headers=viewer, json={"factor": 2}).status_code == 422
        action = client.post(proposal, headers=viewer).json()
        assert action["status"] == "proposed" and action["simulation"] is True
        assert client.post(proposal, headers=viewer).json() == action
        assert client.get(COMMANDS, headers=edge).json()["items"] == []
        action_path = f"/api/v1/remediation/{action['action_id']}"
        assert client.post(action_path + "/rollback", headers=viewer).status_code == 409
        assert client.post(action_path + "/approve", headers=operator(runtime, "beta")).status_code == 404
        approved = client.post(action_path + "/approve", headers=viewer).json()
        assert approved["status"] == "approved"
        assert client.post(action_path + "/approve", headers=viewer).json() == approved
        assert client.get(COMMANDS, headers=viewer).status_code == 403
        assert client.get(COMMANDS, headers=collector_headers(settings(runtime, "beta"))).json()["items"] == []

        def status():
            return client.get(incident_path, headers=viewer).json()

        def audit():
            return client.get(AUDIT, headers=viewer).json()["items"]

        assert status()["proposal"] == approved  # Offline collector leaves it pending.
        assert [row["status"] for row in audit()] == ["approved", "proposed"]
        metrics_path = f"/api/v1/sources/{action['target_source_id']}/metrics"

        def memory(capacity_change, lower, upper, since=None):
            row = next(item for item in audit() if item["reason_code"] == capacity_change)
            cutoff = parse_utc(row["occurred_at"])
            if since is not None:
                cutoff = max(cutoff, since)
            items = client.get(metrics_path, headers=viewer, params={"recent": True}).json()["items"]
            return next((item for item in items if item.get("simulation")
                         and parse_utc(item["event_time_utc"]) > cutoff
                         and lower < item["metrics"]["memory_pct"] < upper), None)

        with process(*launch, stderr=log):
            wait_until(lambda: status()["proposal_status"] == "succeeded")
            recovered = wait_until(lambda: memory("applied", 60, 70))
        with process(*launch, stderr=log):
            # A newly started generation still uses the stored larger capacity.
            restart = utc_now()
            resumed = wait_until(lambda: memory("applied", 60, 70, restart))
            assert resumed["payload_uuid"] != recovered["payload_uuid"]
            wait_until(lambda: status()["status"] == "resolved")
            if os.getenv("CICADA_TEST_DASHBOARD"):
                verify_dashboard_action(client, viewer, action["action_id"])
            else:
                assert client.post(action_path + "/rollback", headers=viewer).json()["status"] in {"rollback_pending", "rolled_back"}
            wait_until(lambda: status()["proposal_status"] == "rolled_back")
            restored = wait_until(lambda: memory("snapshot_restored", 95, 100))
        assert client.post(action_path + "/rollback", headers=viewer).json()["status"] == "rolled_back"
        history = audit()
        assert [row["reason_code"] for row in reversed(history)] == [
            "eligible_memory_incident", "queued_scale", "dispatched", "applied",
            "queued_rollback", "dispatched_rollback", "snapshot_restored",
        ]
        assert history[-1]["actor"].startswith("operator-") and history[0]["actor"] == config.collector_id
        assert client.get(AUDIT, headers=operator(runtime, "beta")).json()["items"] == []
        print(f"Demo memory telemetry before scale {initial_memory}%, after scale {recovered['metrics']['memory_pct']}%, "
              f"after restart {resumed['metrics']['memory_pct']}%, after rollback {restored['metrics']['memory_pct']}%.")


def test_policy_limits_target_and_preserves_rollback_after_quota(service):
    runtime, client, _, _ = service
    config = settings(runtime, "alpha")
    viewer, edge = operator(runtime, "alpha"), collector_headers(config)
    sanitizer = Sanitizer(config)
    base = utc_now() - timedelta(seconds=9)
    sequence = 0

    def send(value, demo=True, node=NODE):
        nonlocal sequence
        sequence += 1
        raw = replace(sample(config, f"action-rate-{sequence}", utc_text(base + timedelta(milliseconds=100 * sequence))),
                      source_key=f"{config.tenant_id}:{node}", metrics={"memory_pct": value})
        payload = sanitizer.metric(raw).model_copy(update={"simulation": True if demo else None})
        return client.post(f"/api/v1/ingest/{config.region}", content=canonical_bytes(payload), headers=edge)

    def incident_path():
        incident = client.get("/api/v1/incidents", headers=viewer).json()["items"][0]
        return f"/api/v1/incidents/{incident['incident_id']}"

    def finish(kind):
        command, = client.get(COMMANDS, headers=edge).json()["items"]
        assert command["kind"] == kind
        assert client.get(COMMANDS, headers=edge).json()["items"] == [command]
        result = {"simulation": True, "outcome": "succeeded",
                  "reason_code": "applied" if kind == "scale" else "snapshot_restored",
                  "before_capacity_mb": 1024 if kind == "scale" else 1536,
                  "after_capacity_mb": 1536 if kind == "scale" else 1024}
        result_path = f"{COMMANDS}/{command['command_id']}/result"
        assert client.post(result_path, headers=viewer, json=result).status_code == 403
        assert client.post(result_path, headers=collector_headers(settings(runtime, "beta")), json=result).status_code == 404
        assert client.post(result_path, headers=edge, json={**result, "after_capacity_mb": 1944}).status_code == 422
        first = client.post(result_path, headers=edge, json=result)
        first.raise_for_status()
        assert client.post(result_path, headers=edge, json=result).json() == first.json()
        assert client.post(result_path, headers=edge, json={**result, "after_capacity_mb": 1944}).status_code == 409

    assert send(98., node="worker-01").status_code == 403
    send(98., demo=False).raise_for_status()
    assert client.post(incident_path() + "/proposal", headers=viewer).status_code == 409
    for _ in range(5):
        send(40., demo=False).raise_for_status()

    for n in range(3):
        send(98.).raise_for_status()
        action = client.post(incident_path() + "/proposal", headers=viewer)
        action.raise_for_status()
        path = f"/api/v1/remediation/{action.json()['action_id']}"
        assert client.post(path + "/approve", headers=viewer).json()["status"] == "approved"
        finish("scale")
        for _ in range(5):
            send(40.).raise_for_status()
        if n == 2:
            send(98.).raise_for_status()
            assert client.post(incident_path() + "/proposal", headers=viewer).status_code == 409
        assert client.post(path + "/rollback", headers=viewer).json()["status"] == "rollback_pending"
        finish("rollback")
    assert client.post(incident_path() + "/proposal", headers=viewer).status_code == 429


def test_local_receipt_survives_lost_ack_without_reapplying(service, tmp_path):
    runtime, _, _, _ = service
    config = settings(runtime, "alpha")
    target = Sanitizer(config).sources[config.demo_memory_source]
    path = tmp_path / "demo.sqlite"
    command = DemoCommand(
        command_id=str(uuid4()), action_id=str(uuid4()), tenant_id=config.tenant_id, collector_id=config.collector_id,
        target_source_id=target, kind="scale", playbook="SCALE_CONTAINER_MEMORY", factor=1.5, simulation=True,
    )

    async def exercise():
        async with CommandRunner.open(path, config, DemoSource()) as runner:
            original = await runner.capacity()
            scaled = await runner.execute(command)
            assert scaled.after_capacity_mb == original * 3 // 2
        async with CommandRunner.open(path, config, DemoSource()) as runner:
            assert await runner.execute(command) == scaled  # ACK was never sent.
            assert await runner.capacity() == scaled.after_capacity_mb
            with pytest.raises(CommandMismatch):
                await runner.execute(command.model_copy(update={"collector_id": "other-collector"}))
            rollback = command.model_copy(update={"command_id": str(uuid4()), "kind": "rollback"})
            result = await runner.execute(rollback)
            assert result.after_capacity_mb == original
        async with CommandRunner.open(path, config, DemoSource()) as runner:
            assert await runner.execute(rollback) == result
            assert await runner.capacity() == original
    asyncio.run(exercise())


def verify_dashboard_action(client, viewer, action_id):
    from playwright.sync_api import expect, sync_playwright

    origin = str(client.base_url).rstrip("/")
    with sync_playwright() as playwright, playwright.chromium.launch(channel=os.getenv("CICADA_TEST_BROWSER")) as browser:
        page = browser.new_page()

        def forward(route):
            request = route.request
            headers = {key: value for key, value in request.all_headers().items()
                       if key in {"authorization", "x-tenant-id", "content-type"}}
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
        expect(page.locator(".action-status-card").get_by_text(action_id, exact=True)).to_be_visible()
        page.locator(".btn-action-rollback").click()
        expect(page.locator(".state-badge").get_by_text("ROLLED_BACK", exact=True)).to_be_visible(timeout=10000)
