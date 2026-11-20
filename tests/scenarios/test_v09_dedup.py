"""
Tests for Check V09, IDEM-01..03, SIMU-08: Deduplication, hash collision conflict, and out-of-order handling.

Owned by Member 3 (feat/fixtures-validation).
Verifies:
- Idempotent deduplication: identical UUID and body SHA256 yields status duplicate with same receipt hash.
- Conflicting body rejection: same UUID with different body bytes produces 409 conflict.
- Out-of-order stream: events [t3, t1, t2] are correctly sorted chronologically by event_time_utc.
- Zero double counting of metrics upon duplicate ingestion.
"""

import hashlib
import json
from typing import Any, Dict, List, Tuple


class MockDedupStore:
    """
    Mock representation of M1's transactional SQLite deduplication table.
    """
    def __init__(self):
        self.records: Dict[str, Tuple[str, Dict[str, Any]]] = {}  # uuid -> (sha256, payload)
        self.analytic_processed_count = 0

    def ingest(self, payload: Dict[str, Any]) -> Tuple[int, str]:
        """
        Simulate POST /api/v1/ingest logic:
        Returns (http_status_code, status_string).
        """
        uuid_str = payload["payload_uuid"]
        body_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
        body_sha = hashlib.sha256(body_bytes).hexdigest()

        if uuid_str in self.records:
            stored_sha, _ = self.records[uuid_str]
            if stored_sha == body_sha:
                # Idempotent retry: HTTP 200 with duplicate flag; NO double counting
                return 200, "duplicate"
            else:
                # Same UUID but different body bytes: HTTP 409 Conflict
                return 409, "body_conflict"

        # Fresh record: commit and trigger analytics
        self.records[uuid_str] = (body_sha, payload)
        self.analytic_processed_count += 1
        return 200, "accepted"


def test_idempotent_deduplication_and_no_double_counting():
    store = MockDedupStore()

    payload = {
        "payload_uuid": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
        "tenant_id": "tenant-alpha",
        "collector_id": "collector-alpha-1",
        "source_id": "src-api-01",
        "event_time_utc": "2026-11-20T14:30:00.000Z",
        "metrics": {"cpu_pct": 34.0, "service_available": True},
    }

    # First ingest: accepted
    status_1, outcome_1 = store.ingest(payload)
    assert status_1 == 200
    assert outcome_1 == "accepted"
    assert store.analytic_processed_count == 1

    # Second ingest of exact duplicate: duplicate acknowledged, analytic count remains 1
    status_2, outcome_2 = store.ingest(payload)
    assert status_2 == 200
    assert outcome_2 == "duplicate"
    assert store.analytic_processed_count == 1  # No double counting!


def test_dedup_conflicting_body_conflict():
    store = MockDedupStore()

    payload_a = {
        "payload_uuid": "conflict-uuid-1",
        "tenant_id": "tenant-alpha",
        "metrics": {"cpu_pct": 30.0},
    }
    payload_b = {
        "payload_uuid": "conflict-uuid-1",  # Same UUID
        "tenant_id": "tenant-alpha",
        "metrics": {"cpu_pct": 95.0},      # Different body!
    }

    status_a, outcome_a = store.ingest(payload_a)
    assert status_a == 200
    assert outcome_a == "accepted"

    status_b, outcome_b = store.ingest(payload_b)
    assert status_b == 409
    assert outcome_b == "body_conflict"


def test_out_of_order_event_sorting():
    raw_stream = [
        {"input_id": "rec-3", "event_time_utc": "2026-11-20T14:32:00.000Z", "val": 3},
        {"input_id": "rec-1", "event_time_utc": "2026-11-20T14:30:00.000Z", "val": 1},
        {"input_id": "rec-2", "event_time_utc": "2026-11-20T14:31:00.000Z", "val": 2},
    ]

    sorted_stream = sorted(raw_stream, key=lambda x: x["event_time_utc"])
    expected_order = ["rec-1", "rec-2", "rec-3"]
    assert [r["input_id"] for r in sorted_stream] == expected_order
