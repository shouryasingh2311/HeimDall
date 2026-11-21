"""Regression coverage for shared browser and CLI import behavior."""

import gzip
import json

import pytest

from backend.collector.adapters.auto_adapter import AutoAdapter, LogImportError, parse_records, parse_timestamp_to_utc
from backend.collector.log_review import analyze_log
from backend.shared.config import CollectorSettings, HealthPolicy


@pytest.mark.asyncio
async def test_browser_and_cli_share_aliases_and_percentage_units(tmp_path):
    body = json.dumps({"data": [{"ts": "1700000000000", "hostname": "api-01",
                                 "cpu": .5, "memory_pct": .5, "net_rx_bps": 20}]}).encode()
    path = tmp_path / "unknown.extension"
    path.write_bytes(gzip.compress(body))
    events = [event async for event in AutoAdapter(source=path).events()]
    _, records, malformed = parse_records(gzip.compress(body))
    assert malformed == 0
    assert records[0][1].event == events[0]
    assert events[0].metrics == {"cpu_pct": 50., "memory_pct": .5, "net_rx_bps": 20.}
    assert events[0].event_time_utc == "2023-11-14T22:13:20.000000Z"


@pytest.mark.parametrize("value", [True, float("inf"), float("nan"), "1e300"])
def test_invalid_timestamp_is_rejected(value):
    assert parse_timestamp_to_utc(value) is None


def test_upload_limits_and_binary_rejection():
    for body in (b"\x00EVTX", gzip.compress(b"x" * (5 * 1024 * 1024 + 1)), b"line\n" * 10001):
        with pytest.raises(LogImportError):
            parse_records(body)


@pytest.mark.asyncio
async def test_historical_text_auth_findings_exclude_private_values():
    settings = CollectorSettings(tenant_id="tenant-alpha", collector_id="collector-alpha-1", region="local",
                                 token="test", local_token="test-local", hmac_key="12" * 32, source_keys=["scope"])
    body = "\n".join(f"2021-04-05T12:00:0{i}Z ERROR Failed password for private-user from 198.51.100.20 port 22"
                     for i in reversed(range(5))).encode()
    report = await analyze_log(body, settings, HealthPolicy())
    assert report["finding_count"] == 1
    assert report["findings"][0]["type"] == "auth_threat"
    assert report["records"]["auth_analyzed"] == 5
    assert all(value not in json.dumps(report) for value in ("private-user", "198.51.100.20", "test-local"))
