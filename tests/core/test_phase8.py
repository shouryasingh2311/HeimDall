"""Exercise the release dashboard and API boundary over verified HTTPS."""

from html.parser import HTMLParser
import os
from uuid import uuid4

import pytest

from test_phase1 import collector_headers, operator, service, settings


class DashboardAssets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.paths = {}

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "script" and values.get("type") == "module":
            self.paths[values["src"]] = "javascript"
        elif tag == "link" and values.get("rel") in {"icon", "stylesheet"}:
            self.paths[values["href"]] = {"icon": "image/svg+xml", "stylesheet": "text/css"}[values["rel"]]


@pytest.mark.skipif(not os.getenv("HEIMDAL_TEST_DASHBOARD"), reason="Needs the built dashboard")
def test_release_dashboard_serves_its_production_assets(service):
    _, client, _, _ = service
    index = client.get("/")
    assert index.status_code == 200
    assert "Heimdal | Operations Dashboard" in index.text
    assert index.headers["cache-control"] == "no-cache"
    assets = DashboardAssets()
    assets.feed(index.text)
    assert set(assets.paths.values()) == {"javascript", "text/css", "image/svg+xml"}
    for path, content_type in assets.paths.items():
        assert path.startswith(("/assets/", "/favicon.svg"))
        response = client.get(path)
        assert response.status_code == 200
        assert content_type in response.headers["content-type"]
    for private_path in ("/saas.json", "/server.key", "/api/local/audit", "/openapi.json"):
        assert client.get(private_path).status_code == 404


def test_dashboard_api_routes_require_the_matching_role_and_disable_caching(service):
    runtime, client, _, _ = service
    alpha = settings(runtime, "alpha")
    collector, viewer = collector_headers(alpha), operator(runtime, "alpha")
    identity = uuid4()
    reads = (
        "/fleet", "/transitions", f"/payloads/{identity}", "/sources/unknown/metrics",
        "/incidents", f"/incidents/{identity}", "/remediation/audit", "/benchmarks", "/scenario-results",
    )
    writes = (
        f"/incidents/{identity}/proposal", f"/remediation/{identity}/approve",
        f"/remediation/{identity}/rollback", "/benchmarks/render",
    )
    for method, paths in (("GET", reads), ("POST", writes)):
        for path in paths:
            url = "/api/v1" + path
            for credential, status in (({}, 401), (collector, 403)):
                response = client.request(method, url, headers=credential)
                assert response.status_code == status, path
                assert response.headers["cache-control"] == "private, no-store"
    fleet = client.get("/api/v1/fleet", headers={**viewer, "Origin": "https://external.invalid"})
    assert fleet.status_code == 200
    assert fleet.headers["cache-control"] == "private, no-store"
    assert "access-control-allow-origin" not in fleet.headers
    assert client.get("/api/v1/collector/commands", headers=viewer).status_code == 403
