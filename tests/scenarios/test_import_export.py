"""
Comprehensive tests for multi-format telemetry import and metadata/proof export.
Validates:
1. AutoAdapter format auto-detection (JSONL, JSON, Envelope JSON, CSV, TSV, GZ).
2. Field mapping via explicit file (--map) and automatic alias guessing.
3. Timestamp parsing: ISO 8601, epoch seconds, epoch milliseconds -> UTC.
4. Ratio-to-percentage normalization (0-1 ratios -> 0-100%).
5. Stable, deterministic UUIDv5 event IDs for replay idempotency.
6. Graceful handling of missing fields and malformed records without crashing.
7. Dry-run CLI (inspect_input) reporting and loud failure on missing/empty files.
8. Central SaaS metadata export (CSV/JSON metrics, transitions, remediation, Markdown/JSON incidents, ZIP bundle).
9. Edge collector egress proof export (approved bytes, SHA-256 digests, receipts).
"""

import asyncio
import gzip
import json
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest

from backend.collector.adapters.auto_adapter import AutoAdapter, parse_timestamp_to_utc
from backend.collector.export_proof import build_egress_proof_from_records
from backend.saas import export as export_engine

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.mark.asyncio
async def test_auto_adapter_jsonl():
    adapter = AutoAdapter(source=FIXTURES_DIR / "sample.jsonl", tenant_id="tenant-alpha")
    events = [ev async for ev in adapter.events()]
    assert len(events) == 3
    assert adapter.detected_format == "jsonl"
    assert adapter.malformed_count == 0
    assert events[0].kind == "metric"
    assert events[0].metrics["cpu_pct"] == 45.2
    assert events[1].metrics["memory_pct"] == 42.5
    assert events[2].kind == "auth"
    assert events[2].auth_success is True
    assert events[2].username == "admin"


@pytest.mark.asyncio
async def test_auto_adapter_json_array():
    adapter = AutoAdapter(source=FIXTURES_DIR / "sample.json", tenant_id="tenant-alpha")
    events = [ev async for ev in adapter.events()]
    assert len(events) == 2
    assert "json" in adapter.detected_format
    assert events[0].source_key == "tenant-alpha:db-01"
    assert events[0].metrics["cpu_pct"] == 78.5
    assert events[1].source_key == "tenant-alpha:worker-01"


@pytest.mark.asyncio
async def test_auto_adapter_json_envelope():
    adapter = AutoAdapter(source=FIXTURES_DIR / "envelope.json", tenant_id="tenant-alpha")
    events = [ev async for ev in adapter.events()]
    assert len(events) == 2
    assert events[0].source_key == "tenant-alpha:api-01"
    assert events[0].metrics["cpu_pct"] == 50.0
    assert events[1].source_key == "tenant-alpha:lb-01"
    assert events[1].metrics["cpu_pct"] == 35.0


@pytest.mark.asyncio
async def test_auto_adapter_csv():
    adapter = AutoAdapter(source=FIXTURES_DIR / "sample.csv", tenant_id="tenant-alpha")
    events = [ev async for ev in adapter.events()]
    assert len(events) == 3
    assert "csv" in adapter.detected_format
    assert events[0].source_key == "tenant-alpha:api-01"
    assert events[0].metrics["cpu_pct"] == 52.3
    assert events[1].source_key == "tenant-alpha:db-01"
    assert events[1].metrics["memory_pct"] == 88.5


@pytest.mark.asyncio
async def test_auto_adapter_tsv():
    adapter = AutoAdapter(source=FIXTURES_DIR / "sample.tsv", tenant_id="tenant-alpha")
    events = [ev async for ev in adapter.events()]
    assert len(events) == 2
    assert "tsv" in adapter.detected_format
    assert events[0].source_key == "tenant-alpha:auth-01"
    assert events[0].metrics["cpu_pct"] == 30.5
    assert events[1].source_key == "tenant-alpha:lb-01"


@pytest.mark.asyncio
async def test_auto_adapter_gzip():
    adapter = AutoAdapter(source=FIXTURES_DIR / "sample.jsonl.gz", tenant_id="tenant-alpha")
    events = [ev async for ev in adapter.events()]
    assert len(events) == 3
    assert adapter.detected_format == "jsonl.gz"
    assert events[0].metrics["cpu_pct"] == 45.2


@pytest.mark.asyncio
async def test_auto_adapter_epoch_and_aliases():
    adapter = AutoAdapter(source=FIXTURES_DIR / "sample_epoch.jsonl", tenant_id="tenant-alpha")
    events = [ev async for ev in adapter.events()]
    assert len(events) == 2
    assert events[0].source_key == "tenant-alpha:api-01"
    assert events[0].metrics["cpu_pct"] == 55.0
    assert events[0].metrics["memory_pct"] == 65.0
    assert events[0].event_time_utc.endswith("Z")
    assert events[1].source_key == "tenant-alpha:worker-01"
    assert events[1].metrics["cpu_pct"] == 25.0
    assert events[1].event_time_utc.endswith("Z")


@pytest.mark.asyncio
async def test_auto_adapter_ratios_to_percentages():
    adapter = AutoAdapter(source=FIXTURES_DIR / "sample_ratios.csv", tenant_id="tenant-alpha")
    events = [ev async for ev in adapter.events()]
    assert len(events) == 2
    # 0.65 -> 65.0, 0.72 -> 72.0, 0.80 -> 80.0
    assert events[0].metrics["cpu_pct"] == 65.0
    assert events[0].metrics["memory_pct"] == 72.0
    assert events[0].metrics["disk_used_pct"] == 80.0
    assert events[1].metrics["cpu_pct"] == 30.0


@pytest.mark.asyncio
async def test_auto_adapter_custom_mapping_file():
    adapter = AutoAdapter(
        source=FIXTURES_DIR / "custom_mapped.csv",
        map_path=FIXTURES_DIR / "custom_map.yaml",
        tenant_id="tenant-alpha",
    )
    events = [ev async for ev in adapter.events()]
    assert len(events) == 2
    assert events[0].source_key == "tenant-alpha:api-01"
    assert events[0].metrics["cpu_pct"] == 58.5
    assert events[0].metrics["memory_pct"] == 64.2
    assert events[0].metrics["disk_used_pct"] == 71.0
    assert events[0].metrics["latency_ms"] == 18.5


@pytest.mark.asyncio
async def test_auto_adapter_stable_event_ids_for_deduplication():
    adapter1 = AutoAdapter(source=FIXTURES_DIR / "sample.jsonl", tenant_id="tenant-alpha")
    events1 = [ev async for ev in adapter1.events()]

    adapter2 = AutoAdapter(source=FIXTURES_DIR / "sample.jsonl", tenant_id="tenant-alpha")
    events2 = [ev async for ev in adapter2.events()]

    assert len(events1) == len(events2)
    for e1, e2 in zip(events1, events2):
        assert e1.input_id == e2.input_id, "Event IDs must be deterministic for replay idempotency"


@pytest.mark.asyncio
async def test_auto_adapter_malformed_and_missing_lines():
    adapter = AutoAdapter(source=FIXTURES_DIR / "malformed.jsonl", tenant_id="tenant-alpha")
    events = [ev async for ev in adapter.events()]
    # malformed.jsonl has 5 lines total: 3 valid JSON objects, 1 syntax error line, 1 non-dict JSON ([1,2,3])
    assert len(events) == 3
    assert adapter.malformed_count == 2


def test_inspect_input_cli_success():
    res = subprocess.run(
        [sys.executable, "-m", "backend.collector.inspect_input", str(FIXTURES_DIR / "sample.jsonl")],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    assert "HEIMDALL TELEMETRY INPUT INSPECTION REPORT" in res.stdout
    assert "Detected Format:    jsonl" in res.stdout
    assert "Valid Records Yielded:  3" in res.stdout


def test_inspect_input_cli_fails_loudly_on_missing_file():
    res = subprocess.run(
        [sys.executable, "-m", "backend.collector.inspect_input", "non_existent_file.jsonl"],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 1
    assert "ERROR" in res.stderr or "ERROR" in res.stdout


def test_inspect_input_cli_fails_loudly_on_empty_file(tmp_path: Path):
    empty_file = tmp_path / "empty.jsonl"
    empty_file.write_text("", encoding="utf-8")
    res = subprocess.run(
        [sys.executable, "-m", "backend.collector.inspect_input", str(empty_file)],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 1
    assert "empty" in (res.stderr + res.stdout).lower()


def test_saas_export_engine():
    # Test CSV string generation
    records = [
        {"ts": "2026-11-20T12:00:00Z", "node": "api-01", "cpu": 45.0},
        {"ts": "2026-11-20T12:00:05Z", "node": "lb-01", "cpu": 30.0},
    ]
    csv_str = export_engine.to_csv_string(records, ["ts", "node", "cpu"])
    lines = csv_str.strip().splitlines()
    assert lines[0] == "ts,node,cpu"
    assert lines[1] == "2026-11-20T12:00:00Z,api-01,45.0"

    # Test Incident Markdown generation
    incidents = [
        {
            "id": "inc-001",
            "title": "High Memory Pressure on auth-01",
            "severity": "CRITICAL",
            "status": "OPEN",
            "evidence_score": 0.94,
            "baseline": "45.0%",
            "z_score": 3.82,
            "recommended_action": "restart_auth_pod",
            "summary": "Memory consumption exceeded 3 standard deviations",
            "created_at_utc": "2026-11-20T12:00:00Z",
            "updated_at_utc": "2026-11-20T12:00:00Z",
        }
    ]
    md = export_engine.generate_incident_markdown(incidents, "tenant-alpha")
    assert "Heimdall AIOps Incident & Threat Report" in md
    assert "tenant-alpha" in md
    assert "High Memory Pressure on auth-01" in md
    assert "3.82" in md
    assert "restart_auth_pod" in md

    # Test Zip bundle generation
    bundle = export_engine.build_export_zip(
        metrics_records=[{"observed_at_utc": "2026-11-20T12:00:00Z", "source_id": "api-01", "cpu_pct": 50}],
        transitions_records=[],
        incidents_records=incidents,
        remediation_records=[],
        tenant_id="tenant-alpha",
    )
    assert len(bundle) > 0
    # Verify zip content
    import io
    zf = zipfile.ZipFile(io.BytesIO(bundle), "r")
    names = zf.namelist()
    assert "metrics.csv" in names
    assert "incident_report.md" in names
    assert "incidents.json" in names


def test_egress_proof_generation():
    sample_records = [
        {
            "approved_bytes": 1024,
            "sha256_hex": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "receipt_ack": "receipt-test-123",
            "source_id": "api-01",
            "delivered_at_utc": "2026-11-20T12:00:00Z",
        }
    ]
    proof = build_egress_proof_from_records("tenant-alpha", sample_records)
    assert proof["tenant_id"] == "tenant-alpha"
    assert proof["records_count"] == 1
    assert proof["records"][0]["approved_bytes"] == 1024
    assert proof["records"][0]["receipt_ack"] == "receipt-test-123"
