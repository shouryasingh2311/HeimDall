"""Verify health, tenant isolation, timestamps and browser timing against live APIs."""

from datetime import timedelta
import os
import time
from uuid import uuid4

import pytest

from backend.collector.sanitizer import Sanitizer
from backend.saas.health import source_health
from backend.shared.config import HealthPolicy
from backend.shared.models import CollectorHeartbeat, Metrics, canonical_bytes, parse_utc, utc_now, utc_text
from test_phase1 import collector_headers, operator, process, sample, service, settings

NOMINAL = dict(cpu_pct=22., memory_pct=25., disk_used_pct=40., latency_ms=10., packet_loss_pct=0.,
               connectivity=True, service_available=True)


@pytest.mark.parametrize(("field", "value", "state"), [
    ("cpu_pct", 69.99, "Excellent"), ("cpu_pct", 70., "Good"), ("cpu_pct", 85., "Fair"), ("cpu_pct", 95., "Poor"),
    ("memory_pct", 70., "Good"), ("memory_pct", 85., "Fair"), ("memory_pct", 95., "Poor"),
    ("disk_used_pct", 75., "Good"), ("disk_used_pct", 90., "Fair"), ("disk_used_pct", 98., "Poor"),
    ("latency_ms", 50., "Good"), ("latency_ms", 120., "Fair"), ("latency_ms", 500., "Poor"),
    ("packet_loss_pct", 0.01, "Good"), ("packet_loss_pct", 2., "Fair"), ("packet_loss_pct", 10., "Poor"),
    ("connectivity", False, "Poor"), ("service_available", False, "Poor"), ("memory_pct", None, "Fair"),
])
def test_health_boundaries(field, value, state):
    metrics = Metrics(**{**NOMINAL, field: value})
    assert source_health(HealthPolicy(), "source", metrics, 0, False)[0] == state


def test_missing_freshness_risk_and_precedence():
    metrics, policy = Metrics(**NOMINAL), HealthPolicy()
    assert source_health(policy, "source", metrics, 29.99, False)[0] == "Excellent"
    assert source_health(policy, "source", metrics, 30, False)[0] == "Fair"
    assert source_health(policy, "source", metrics, 55, False)[0] == "Poor"
    assert source_health(policy, "source", metrics, 0, True)[0] == "Fair"
    assert source_health(policy, "source", metrics, 0, False, 50)[0] == "Fair"
    assert source_health(policy, "source", metrics, 30, True, 90) == (
        "Poor", ["security_risk", "config_invalid", "source_stale"],
    )
    custom = HealthPolicy(cpu=[10., 30., 40.])
    assert source_health(custom, "source", metrics, 0, False)[0] == "Good"


def heartbeat(config, now=None):
    return CollectorHeartbeat(
        schema_version=1, tenant_id=config.tenant_id, collector_id=config.collector_id,
        region=config.region, heartbeat_uuid=str(uuid4()), generated_at_utc=utc_text(now or utc_now()),
        source_timezone="UTC", version="0.1.0", rss_mb=40., cpu_pct=1., queue_depth=0, config_status="valid",
    )


def test_watchdog_offline_without_browser_polling(service):
    runtime, client, _, _ = service
    config = settings(runtime, "alpha")
    collector, viewer = collector_headers(config), operator(runtime, "alpha")
    beat = heartbeat(config)
    endpoint = "/api/v1/heartbeats"
    assert client.post(endpoint, content=canonical_bytes(beat), headers=collector).json()["refreshed"]
    assert not client.post(endpoint, content=canonical_bytes(beat), headers=collector).json()["refreshed"]
    assert client.post(
        endpoint, content=canonical_bytes(heartbeat(config, utc_now() - timedelta(seconds=16))), headers=collector,
    ).status_code == 422
    time.sleep(65)
    # Read history before GET /fleet, which is also allowed to refresh health.
    history = client.get("/api/v1/transitions", headers=viewer).json()["items"]
    assert len(history) == 1
    transition = history[0]
    delay = (parse_utc(transition["timestamp_utc"]) - parse_utc(beat.generated_at_utc)).total_seconds()
    assert 55 <= delay <= 60
    assert (transition["from_state"], transition["to_state"], transition["reason_codes"]) == (
        "Excellent", "Poor", ["heartbeat_expired"],
    )
    print(f"Watchdog offline detection: {delay:.3f}s from last heartbeat")
    result = client.get("/api/v1/benchmarks", headers=viewer).json()
    assert result["offline"][0]["delay_ms"] == pytest.approx(delay * 1000, abs=.01)
    assert client.get("/api/v1/transitions", headers=operator(runtime, "beta")).json()["items"] == []
    assert client.post(endpoint, content=canonical_bytes(heartbeat(config)), headers=collector).json()["refreshed"]
    assert client.get("/api/v1/transitions", headers=viewer).json()["items"][0]["to_state"] == "Excellent"


def test_network_health_history_replay_and_benchmark_ingest(service):
    runtime, client, _, _ = service
    config = settings(runtime, "alpha")
    collector, viewer = collector_headers(config), operator(runtime, "alpha")
    sanitizer = Sanitizer(config)
    endpoint = f"/api/v1/ingest/{config.region}"

    def send(name, seconds_old, **changes):
        raw = sample(config, name, utc_text(utc_now() - timedelta(seconds=seconds_old)))
        raw.metrics = {**NOMINAL, **changes}
        data = sanitizer.metric(raw)
        response = client.post(endpoint, content=canonical_bytes(data), headers=collector)
        response.raise_for_status()
        return data

    send("healthy", 2)
    breach = send("loss", 1, packet_loss_pct=10.)
    stale = send("stale", 40)
    assert client.get("/api/v1/fleet", headers=viewer).json()["sources"][0]["health"] == "Poor"
    assert client.get("/api/v1/transitions", headers=viewer).json()["items"][0]["reason_codes"] == ["packet_loss"]
    metrics = client.get(f"/api/v1/sources/{breach.source_id}/metrics", headers=viewer, params={"recent": True, "limit": 2})
    assert [item["payload_uuid"] for item in metrics.json()["items"]][-1] == breach.payload_uuid

    render_path = "/api/v1/benchmarks/render"
    receipt = dict(run_id="test-run", session_id="browser-a", payload_uuid=breach.payload_uuid,
                   rendered_at_utc=utc_text(utc_now()))
    assert client.post(render_path, headers=collector, json=receipt).status_code == 403
    assert client.post(render_path, headers=operator(runtime, "beta"), json=receipt).status_code == 404
    assert client.post(render_path, headers=viewer, json=receipt).json()["first_recorded"]
    assert not client.post(render_path, headers=viewer, json=receipt).json()["first_recorded"]
    flagged = {**receipt, "payload_uuid": stale.payload_uuid, "rendered_at_utc": stale.event_time_utc}
    assert client.post(render_path, headers=viewer, json=flagged).status_code == 200
    summary = client.get("/api/v1/benchmarks", params={"run_id": "test-run"}, headers=viewer).json()
    assert summary["all"]["eligible"] == 3
    assert summary["live"]["samples"] == 1
    assert summary["all"]["missing"] == 1
    assert summary["replay_or_delayed"]["clock_flagged"] == 1
    assert 1000 <= summary["live"]["p95_ms"] <= 10000

    active_beat = heartbeat(config).model_copy(update={"config_status": "invalid"})
    assert client.post("/api/v1/heartbeats", content=canonical_bytes(active_beat), headers=collector).status_code == 200
    assert client.get("/api/v1/fleet", headers=viewer).json()["collectors"][0]["health"] == "Fair"
    for age in (70, 40):
        raw = sample(config, f"older-{age}", utc_text(utc_now() - timedelta(seconds=age)))
        raw.source_key = config.source_keys[1]
        raw.metrics = NOMINAL
        payload = sanitizer.metric(raw)
        assert client.post(endpoint, content=canonical_bytes(payload), headers=collector).json()["analysis_status"] == "historical"
        states = client.get("/api/v1/fleet", headers=viewer).json()
        source = next(row for row in states["sources"] if row["source_id"] == payload.source_id)
        assert source["health"] == "Poor" and "no_live_telemetry" in source["reason_codes"]


@pytest.mark.skipif(not os.getenv("CICADA_TEST_DASHBOARD"), reason="Needs the built dashboard and a browser")
def test_real_dashboard_render_benchmark(service):
    from playwright.sync_api import sync_playwright

    runtime, client, _, _ = service
    viewer = operator(runtime, "alpha")
    origin = str(client.base_url).rstrip("/")
    with process("backend.collector.daemon", "--runtime", runtime), sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel=os.getenv("CICADA_TEST_BROWSER"))
        with browser:
            page = browser.new_page(viewport={"width": 1600, "height": 1800})

            def forward(route):
                request = route.request
                forwarded = {key: value for key, value in request.all_headers().items()
                             if key in {"authorization", "x-tenant-id", "content-type"}}
                response = client.request(request.method, request.url.removeprefix(origin),
                                          headers=forwarded, content=request.post_data_buffer)
                route.fulfill(status=response.status_code, body=response.content,
                              content_type=response.headers.get("content-type", "application/octet-stream"))

            page.route(f"{origin}/**", forward)
            page.goto(origin)
            page.get_by_label("Tenant ID").fill(viewer["X-Tenant-ID"])
            page.get_by_label("Operator token").fill(viewer["Authorization"].split()[1])
            page.get_by_role("button", name="Connect dashboard").click()
            page.locator("tr[data-payload-uuid]").first.wait_for()
            deadline = time.monotonic() + 75
            while True:
                page.wait_for_timeout(1000)
                timing = client.get("/api/v1/benchmarks", headers=viewer).json()
                if timing["live"]["samples"] >= 100 or time.monotonic() >= deadline:
                    break
            print(f"Browser timing: {timing['live']}")
            assert timing["live"]["samples"] >= 100
            assert timing["live"]["p95_ms"] <= 10000
            page.get_by_text("Measured render timing", exact=True).wait_for()
