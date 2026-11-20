"""Phase 1 checks against actual collector and HTTPS API processes."""

from contextlib import contextmanager
from datetime import timedelta
import hashlib
import json
import os
from pathlib import Path
import socket
import sqlite3
import ssl
import subprocess
import sys
import time

import httpx
import pytest

from backend.collector.demo_source import RawEvent
from backend.collector.sanitizer import Sanitizer
from backend.shared.config import CollectorSettings, read_settings
from backend.shared.models import canonical_bytes, utc_now, utc_text
from scripts.security.bootstrap import bootstrap

ROOT = Path(__file__).resolve().parents[2]


@contextmanager
def process(module, *args, stderr=None):
    with subprocess.Popen(
        [sys.executable, "-m", module, *map(str, args)], cwd=ROOT,
        stdout=subprocess.DEVNULL, stderr=stderr or subprocess.DEVNULL,
    ) as proc:
        try:
            yield proc
        finally:
            if proc.poll() is None:
                proc.terminate()
                proc.wait(timeout=10)


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def headers(tenant, token):
    return {"X-Tenant-ID": tenant, "Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def operator(runtime, tenant):
    record = json.loads((runtime / f"operator-{tenant}.json").read_text())
    return headers(record["tenant_id"], record["token"])


def collector_headers(config):
    return headers(config.tenant_id, config.token.get_secret_value())


def settings(runtime, tenant):
    return read_settings(runtime / f"collector-{tenant}.json", CollectorSettings)


def wait_for(client, path, proc, request_headers=None):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and proc.poll() is None:
        try:
            response = client.get(path, headers=request_headers)
            if response.status_code == 200:
                return response
        except httpx.TransportError:
            pass
        time.sleep(0.1)
    pytest.fail(f"Service unavailable at {path} (process status {proc.poll()})")


@pytest.fixture
def service(tmp_path):
    runtime, port, local_port = tmp_path / "runtime", free_port(), free_port()
    bootstrap(runtime, port, local_port)
    tls = ssl.create_default_context(cafile=str(runtime / "ca.pem"))
    dashboard = os.getenv("HEIMDAL_TEST_DASHBOARD")
    args = ["--runtime", runtime, "--port", port]
    if dashboard:
        args += ["--dashboard", Path(dashboard).resolve()]
    with (tmp_path / "server.log").open("w") as log:
        with process("backend.saas.main", *args, stderr=log) as proc:
            with httpx.Client(base_url=f"https://localhost:{port}", verify=tls, trust_env=False) as client:
                wait_for(client, "/healthz", proc)
                yield runtime, client, port, local_port


def sample(config, identity="test-record", time_utc=None):
    return RawEvent(
        source_key=config.source_keys[0], tenant_id=config.tenant_id, collector_id=config.collector_id,
        input_id=identity, event_time_utc=time_utc or utc_text(utc_now()), source_timezone="Asia/Kolkata",
        metrics={"cpu_pct": 24.7, "service_available": True, "unapproved": "synthetic-sensitive-value"},
        raw_text="synthetic-secret=fixture-local-only <script>not HTML</script>",
    )


def test_verified_https_and_credential_scope(service):
    runtime, client, port, _ = service
    alpha = settings(runtime, "alpha")
    beta = settings(runtime, "beta")
    payload = Sanitizer(alpha).metric(sample(alpha))
    wire = canonical_bytes(payload)
    endpoint = f"/api/v1/ingest/{alpha.region}"
    op_alpha = operator(runtime, "alpha")
    op_beta = operator(runtime, "beta")
    auth_alpha, auth_beta = collector_headers(alpha), collector_headers(beta)

    assert client.get("/healthz").json() == {"status": "ok"}
    with httpx.Client(trust_env=False) as unrelated_trust, pytest.raises(httpx.ConnectError, match="CERTIFICATE_VERIFY_FAILED"):
        unrelated_trust.get(f"https://localhost:{port}/healthz")
    tls = ssl.create_default_context(cafile=str(runtime / "ca.pem"))
    with socket.create_connection(("127.0.0.1", port)) as conn:
        with pytest.raises(ssl.SSLCertVerificationError, match="Hostname mismatch"):
            tls.wrap_socket(conn, server_hostname="wrong.invalid")

    assert client.post(endpoint, content=wire).status_code == 401
    bad_token = headers(alpha.tenant_id, "invalid")
    assert client.post(endpoint, content=wire, headers=bad_token).status_code == 401
    assert client.post(endpoint, content=wire, headers=op_alpha).status_code == 403
    assert client.get("/api/v1/fleet", headers=auth_alpha).status_code == 403
    assert client.post(endpoint, content=wire, headers=auth_beta).status_code == 403
    assert client.post(endpoint, content=wire, headers={**auth_alpha, "X-Tenant-ID": beta.tenant_id}).status_code == 403
    assert client.post(f"/api/v1/ingest/{beta.region}", content=wire, headers=auth_alpha).status_code == 403
    foreign_source = Sanitizer(beta).metric(sample(beta)).source_id
    for field, value in (("source_id", foreign_source), ("collector_id", beta.collector_id), ("region", beta.region)):
        forged = {**payload.model_dump(), field: value}
        assert client.post(endpoint, json=forged, headers=auth_alpha).status_code == 403

    for metrics in ({"cpu_pct": "synthetic-sensitive-value"}, {"cpu_pct": 2, "private": "synthetic-sensitive-value"}):
        response = client.post(endpoint, json={**payload.model_dump(), "metrics": metrics}, headers=auth_alpha)
        assert response.status_code == 422
        assert "synthetic-sensitive-value" not in response.text
    duplicate_key = wire[:-1] + b',"source_timezone":"UTC"}'
    assert client.post(endpoint, content=duplicate_key, headers=auth_alpha).status_code == 422
    assert client.post(endpoint, content=iter([b" " * 9000, b" " * 9000]), headers=auth_alpha).status_code == 413

    first = client.post(endpoint, content=wire, headers=auth_alpha)
    assert first.status_code == 200
    assert first.json()["status"] == "accepted"
    assert first.json()["body_sha256"] == hashlib.sha256(wire).hexdigest()
    assert client.post(endpoint, content=wire, headers=auth_alpha).json()["status"] == "duplicate"
    conflict = {**payload.model_dump(), "metrics": {"cpu_pct": 99}}
    assert client.post(endpoint, json=conflict, headers=auth_alpha).status_code == 409

    detail_path = f"/api/v1/payloads/{payload.payload_uuid}"
    assert client.get(detail_path, headers=op_alpha).json()["body_sha256"] == first.json()["body_sha256"]
    assert client.get(detail_path, headers=op_beta).status_code == 404
    assert client.get(f"/api/v1/sources/{payload.source_id}/metrics", headers=op_beta).status_code == 404
    assert client.get("/api/v1/fleet", headers=op_beta).json()["sources"] == []
    assert client.get("/api/v1/fleet", headers=op_alpha).json()["sources"][0]["payload_uuid"] == payload.payload_uuid
    with sqlite3.connect(runtime / "saas.sqlite") as db:
        assert db.execute("SELECT body FROM metadata").fetchall() == [(wire,)]


def test_live_collector_privacy_and_browser_slice(service, tmp_path):
    runtime, client, _, local_port = service
    alpha = settings(runtime, "alpha")
    input_path = tmp_path / "local.jsonl"
    raw = sample(alpha)
    input_path.write_text(json.dumps(raw.to_dict()) + "\n", encoding="utf-8")
    payload = Sanitizer(alpha).metric(raw)
    local_headers = {"Authorization": f"Bearer {alpha.local_token.get_secret_value()}"}
    app_headers = operator(runtime, "alpha")
    payload_path = f"/api/v1/payloads/{payload.payload_uuid}"

    with (tmp_path / "collector.log").open("w") as log:
        with process("backend.collector.daemon", "--runtime", runtime, "--input", input_path, stderr=log) as proc:
            with httpx.Client(base_url=f"http://127.0.0.1:{local_port}", trust_env=False) as local:
                wait_for(local, "/audit", proc)
                central = wait_for(client, payload_path, proc, app_headers).json()
                assert local.get("/api/local/audit").status_code == 401
                assert local.get("/api/local/audit", headers={**local_headers, "Origin": "https://outside.invalid"}).status_code == 403
                assert local.get("/api/local/audit", headers={**local_headers, "Host": "outside.invalid"}).status_code == 403
                for _ in range(20):
                    latest = local.get("/api/local/audit", headers=local_headers).json()["items"][0]
                    if latest["state"] == "acknowledged":
                        break
                    time.sleep(0.05)
                assert latest["raw_preview"] == "synthetic-secret=[REDACTED] <script>not HTML</script>"
                assert latest["state"] == "acknowledged"
                assert latest["approved_body"].encode() == canonical_bytes(payload)
                assert latest["body_sha256"] == central["body_sha256"] == latest["receipt"]["body_sha256"]
                assert "synthetic-secret" not in json.dumps(central)
                assert "synthetic-sensitive-value" not in latest["approved_body"]
                assert client.get("/api/local/audit", headers=app_headers).status_code == 404
                fleet = wait_for(client, "/api/v1/fleet", proc, app_headers).json()
                assert fleet["collectors"][0]["collector_id"] == alpha.collector_id
                local_match = local.get(
                    "/api/local/audit", params={"payload_uuid": payload.payload_uuid}, headers=local_headers,
                ).json()["items"][0]
                assert local_match == latest
                if os.getenv("HEIMDAL_TEST_DASHBOARD"):
                    verify_dashboard(client, app_headers, local, local_headers, local_match)


def verify_dashboard(client, app_headers, local, local_headers, proof):
    from playwright.sync_api import expect, sync_playwright

    # Forward through a CA-verified client without rewriting browser credentials.
    origin = str(client.base_url).rstrip("/")
    with sync_playwright() as playwright:
        channel = os.getenv("HEIMDAL_TEST_BROWSER")
        browser = playwright.chromium.launch(channel=channel)
        with browser:
            page = browser.new_page()

            def forward(route):
                path = route.request.url.removeprefix(origin)
                forwarded = {
                    key: value for key, value in route.request.all_headers().items()
                    if key in {"authorization", "x-tenant-id", "content-type"}
                }
                response = client.request(
                    route.request.method, path, headers=forwarded, content=route.request.post_data_buffer,
                )
                route.fulfill(
                    status=response.status_code, body=response.content,
                    content_type=response.headers.get("content-type", "application/octet-stream"),
                )

            page.route(f"{origin}/**", forward)
            local_page = browser.new_page()
            local_page.goto(f"{str(local.base_url).rstrip('/')}/audit")
            local_page.get_by_label("Local session token").fill(local_headers["Authorization"].split()[1])
            local_page.get_by_label("Payload UUID (optional)").fill(proof["payload_uuid"])
            local_page.get_by_role("button", name="Fetch local evidence").click()
            expect(local_page.locator("#identity")).to_contain_text(proof["body_sha256"])
            uuid, digest = local_page.locator("#identity").inner_text().splitlines()
            expect(local_page.locator("#approved")).to_have_text(proof["approved_body"])
            expect(local_page.locator("#raw")).to_contain_text("<script>not HTML</script>")
            expect(local_page.locator("#raw script")).to_have_count(0)
            page.goto(origin)
            page.get_by_label("Tenant ID").fill(app_headers["X-Tenant-ID"])
            page.get_by_label("Operator token").fill(app_headers["Authorization"].split()[1])
            page.get_by_role("button", name="Connect dashboard").click()
            page.get_by_role("button", name="View Trends").first.click()
            expect(page.get_by_role("dialog").get_by_text(proof["body_sha256"][:12] + "...")).to_be_visible()
            page.get_by_role("button", name="Close dialog").click()
            page.get_by_role("tab", name="Payload Egress Inspector", exact=True).click()
            page.get_by_label("Inspect Payload UUIDv5").fill(uuid)
            page.get_by_role("button", name="Inspect Metadata").click()
            expect(page.get_by_text(digest, exact=True)).to_be_visible()
            page.get_by_label("Local collector SHA-256 digest").fill("0" * 64)
            expect(page.get_by_text("DIGEST MISMATCH:", exact=True)).to_be_visible()
            page.get_by_label("Local collector SHA-256 digest").fill(digest)
            expect(page.get_by_text("DIGEST MATCH CONFIRMED:", exact=True)).to_be_visible()
            expect(page.get_by_text("synthetic-secret", exact=False)).to_have_count(0)


def test_event_order_and_pagination(service):
    runtime, client, _, _ = service
    config = settings(runtime, "alpha")
    sanitizer = Sanitizer(config)
    now = utc_now()
    recent, tied = sorted(
        (sanitizer.metric(sample(config, name, utc_text(now))) for name in ("recent", "tied")),
        key=lambda payload: payload.payload_uuid,
    )
    earlier = sanitizer.metric(sample(config, "earlier", utc_text(now - timedelta(seconds=1))))
    post = f"/api/v1/ingest/{config.region}"
    assert client.post(post, content=canonical_bytes(recent), headers=collector_headers(config)).status_code == 200
    replay = client.post(post, content=canonical_bytes(earlier), headers=collector_headers(config))
    assert replay.json()["analysis_status"] == "historical"
    read = f"/api/v1/sources/{recent.source_id}/metrics"
    auth = operator(runtime, "alpha")
    first = client.get(read, params={"limit": 1}, headers=auth).json()
    assert first["items"][0]["payload_uuid"] == earlier.payload_uuid
    following = client.get(read, params={"cursor": first["next_cursor"]}, headers=auth).json()
    assert following["items"][0]["payload_uuid"] == recent.payload_uuid
    assert following["next_cursor"] is None
    assert client.get("/api/v1/fleet", headers=auth).json()["sources"][0]["payload_uuid"] == recent.payload_uuid

    replay = client.post(post, content=canonical_bytes(tied), headers=collector_headers(config))
    assert replay.json()["analysis_status"] == "historical"
    assert client.get("/api/v1/fleet", headers=auth).json()["sources"][0]["payload_uuid"] == recent.payload_uuid
