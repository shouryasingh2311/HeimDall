"""Rehearse all eight scenarios against real local and central services."""

from datetime import timedelta
import os
import sqlite3
import subprocess
import sys
import time
from uuid import uuid4

import httpx

from backend.shared.models import utc_now, utc_text
from test_phase1 import collector_headers, operator, process, service, settings, wait_for


def test_expired_scenario_is_blocked_until_collector_reports_completion(service):
    runtime, central, _, _ = service
    edge = collector_headers(settings(runtime, "alpha"))
    viewer = operator(runtime, "alpha")
    endpoint = "/api/v1/scenario-results"
    now = utc_now()
    for number, age, expected in ((1, 100, "blocked"), (2, 5, "running"), (8, 190, "running")):
        active = dict(run_id=str(uuid4()), scenario_id=number, status="running",
                      started_at_utc=utc_text(now - timedelta(seconds=age)))
        central.post(endpoint, headers=edge, json=active).raise_for_status()
        current = next(row for row in central.get(endpoint, headers=viewer).json() if row["scenario_id"] == number)
        assert current["status"] == expected and current["run_id"] == active["run_id"]
        if expected == "blocked":
            assert current["reason_code"] == "result_not_reported"
            finished = dict(active, status="failed", finished_at_utc=utc_text(now), reason_code="evidence_timeout")
            central.post(endpoint, headers=edge, json=finished).raise_for_status()
            latest = central.get(endpoint, headers=viewer).json()[0]
            assert latest["status"] == "failed" and latest["reason_code"] == "evidence_timeout"

    assert central.get(endpoint, headers=operator(runtime, "beta")).json() == []
    bad_time = dict(active, run_id=str(uuid4()), started_at_utc="2026-02-30T12:00:00Z")
    assert central.post(endpoint, headers=edge, json=bad_time).status_code == 422
    future = dict(bad_time, started_at_utc=utc_text(now + timedelta(hours=1)))
    assert central.post(endpoint, headers=edge, json=future).status_code == 422


def test_live_scenarios_repeat_and_report_only_observed_results(service, tmp_path):
    runtime, central, _, port = service
    config = settings(runtime, "alpha")
    viewer = operator(runtime, "alpha")
    local_auth = {"Authorization": f"Bearer {config.local_token.get_secret_value()}"}
    with (tmp_path / "scenario-collector.log").open("w") as log, process(
        "backend.collector.daemon", "--runtime", runtime, "--scenarios", stderr=log,
    ) as proc, httpx.Client(base_url=f"http://127.0.0.1:{port}", trust_env=False) as local:
        wait_for(local, "/api/local/scenarios", proc, local_auth)
        assert "Heimdal local scenarios" in local.get("/scenarios").text
        assert local.post("/api/local/scenarios/1").status_code == 401
        assert local.post("/api/local/scenarios/1", headers={**local_auth, "Origin": "https://example.invalid"}).status_code == 403
        assert local.post("/api/local/scenarios/9", headers=local_auth).status_code == 422

        def start(scenario):
            request = local.post(f"/api/local/scenarios/{scenario}", headers=local_auth)
            assert request.status_code == 202, request.text
            assert request.json()["status"] == "running"
            return request.json()["run_id"]

        def finish(run_id, timeout=65):
            deadline = time.monotonic() + timeout
            state = None
            while time.monotonic() < deadline:
                state = local.get("/api/local/scenarios", headers=local_auth).json()
                result = state["result"]
                if result["run_id"] == run_id and result["status"] != "running" and not state["publishing"]:
                    assert result["status"] == "passed", result
                    return result
                time.sleep(.2)
            raise AssertionError(f"Scenario did not finish: {state}")

        results = {}
        for number in (1, 3, 5, 4, 7, 6, 2):
            run_id = start(number)
            if number == 2:
                assert local.post("/api/local/reset", headers=local_auth).status_code == 409
                assert local.post("/api/local/scenarios/1", headers=local_auth).status_code == 409
            results[number] = finish(run_id)
        assert len(results[2]["payload_uuids"]) == 75
        assert results[7]["duplicate_count"] == 1

        run_id = start(8)
        deadline = time.monotonic() + 20
        action = None
        while time.monotonic() < deadline:
            incidents = central.get("/api/v1/incidents", headers=viewer).json()["items"]
            for incident in incidents:
                path = "/api/v1/incidents/" + incident["incident_id"]
                if central.get(path, headers=viewer).json()["remediation_eligible"]:
                    action = central.post(path + "/proposal", headers=viewer).json()
                    break
            if action:
                break
            time.sleep(.2)
        assert action and action["status"] == "proposed"
        action_url = "/api/v1/remediation/" + action["action_id"]
        assert central.post(action_url + "/approve", headers=viewer).json()["status"] == "approved"
        assert local.post("/api/local/reset", headers=local_auth).status_code == 409
        deadline = time.monotonic() + 22
        recovered = False
        while time.monotonic() < deadline:
            detail = central.get("/api/v1/incidents/" + action["incident_id"], headers=viewer).json()
            if detail["proposal_status"] == "succeeded" and detail["status"] == "resolved":
                recovered = True
                break
            time.sleep(.25)
        assert recovered
        assert central.post(action_url + "/rollback", headers=viewer).json()["status"] == "rollback_pending"
        results[8] = finish(run_id, timeout=20)

        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            reset = local.post("/api/local/reset", headers=local_auth)
            if reset.status_code == 200:
                break
            time.sleep(.1)
        assert reset.status_code == 200, reset.text
        repeat = finish(start(1))
        assert repeat["run_id"] != results[1]["run_id"]
        assert repeat["payload_uuids"] != results[1]["payload_uuids"]
        listed = central.get("/api/v1/scenario-results", headers=viewer).json()
        assert [row["scenario_id"] for row in listed] == list(range(1, 9))
        assert len({row["run_id"] for row in listed}) == 8
        assert all(row["status"] == "passed" for row in listed)
        assert central.get("/api/v1/scenario-results", headers=operator(runtime, "beta")).json() == []
        assert central.get("/api/v1/scenario-results", headers=collector_headers(config)).status_code == 403
        assert central.post("/api/v1/scenario-results", headers=viewer, json=repeat).status_code == 403
        assert central.post("/api/v1/scenario-results", headers=collector_headers(config),
                            json={**repeat, "status": "failed"}).status_code == 409
        with sqlite3.connect(runtime / "saas.sqlite") as db:
            assert db.execute("SELECT count(*) FROM scenario_result").fetchone()[0] == 9
        report = subprocess.run(
            [sys.executable, "-m", "scripts.verification.run_scenarios", "--runtime", str(runtime)],
            capture_output=True, text=True, check=True,
        )
        assert "8. Demo remediation: passed" in report.stdout and "V00: BLOCKED" in report.stdout
        if os.getenv("HEIMDAL_TEST_DASHBOARD"):
            verify_scenario_dashboard(central, viewer, operator(runtime, "beta"))


def verify_scenario_dashboard(client, alpha, beta):
    from playwright.sync_api import expect, sync_playwright

    origin = str(client.base_url).rstrip("/")
    with sync_playwright() as playwright, playwright.chromium.launch(channel=os.getenv("HEIMDAL_TEST_BROWSER")) as browser:
        page = browser.new_page()
        hold_scenarios = False
        pending_scenarios = []

        def forward(route):
            request = route.request
            if hold_scenarios and request.url == f"{origin}/api/v1/scenario-results":
                pending_scenarios.append(route)
                return
            headers = {key: value for key, value in request.all_headers().items()
                       if key in {"authorization", "x-tenant-id", "content-type"}}
            response = client.request(request.method, request.url.removeprefix(origin), headers=headers,
                                      content=request.post_data_buffer)
            route.fulfill(status=response.status_code, body=response.content,
                          content_type=response.headers.get("content-type", "application/octet-stream"))

        page.route(f"{origin}/**", forward)
        page.goto(origin)

        def open_scenarios(viewer):
            page.get_by_label("Tenant ID").fill(viewer["X-Tenant-ID"])
            page.get_by_label("Operator token").fill(viewer["Authorization"].split()[1])
            page.get_by_role("button", name="Connect dashboard").click()
            page.get_by_role("tab", name="Scenario Verification (1–8)").click()

        open_scenarios(alpha)
        expect(page.get_by_text("8 / 8", exact=True)).to_be_visible()
        expect(page.get_by_text("Operator-approved simulation and rollback (V11)", exact=True)).to_be_visible()
        page.get_by_role("button", name="Sign out").click()
        open_scenarios(beta)
        expect(page.get_by_text("No scenario verification results reported yet.", exact=False)).to_be_visible()
        expect(page.get_by_text("8 / 8", exact=True)).to_have_count(0)
        page.get_by_role("button", name="Use Mock Fixtures").click()
        expect(page.get_by_text("fixture-scenario-1", exact=False)).to_be_visible()
        hold_scenarios = True
        page.get_by_role("button", name="Switch to Live API").click()
        expect(page.get_by_text("fixture-scenario-1", exact=False)).to_have_count(0)
        expect(page.get_by_text("8 / 8", exact=True)).to_have_count(0)
        hold_scenarios = False
        for route in pending_scenarios:
            forward(route)
        expect(page.get_by_text("No scenario verification results reported yet.", exact=False)).to_be_visible()
        page.get_by_role("button", name="Sign out").click()
        open_scenarios(alpha)
        expect(page.get_by_text("8 / 8", exact=True)).to_be_visible()
