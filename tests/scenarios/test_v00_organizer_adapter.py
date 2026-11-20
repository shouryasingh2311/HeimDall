"""
Tests for Check V00 and SIMU-01: Organizer stream ingestion & labelled fallback.

Owned by Member 3 (feat/fixtures-validation).
Verifies:
- Live organizer input is adapted with timestamp and identity preserved.
- When unconfirmed/absent, operates in DEMO_FALLBACK mode with gap disclosed.
- Malformed records increment malformed_count rather than crashing.
"""

import asyncio
import json
from pathlib import Path

from backend.collector.adapters.organizer_adapter import OrganizerAdapter


def test_organizer_adapter_fallback_mode_when_no_stream():
    """Verify default behavior when external organizer stream is not provided."""
    async def _test():
        adapter = OrganizerAdapter(organizer_stream_path=None, tenant_id="tenant-alpha")
        status = adapter.get_status()

        assert adapter.is_fallback is True
        assert status["mode"] == OrganizerAdapter.MODE_FALLBACK
        assert "fallback" in status["status_description"].lower()

        events = []
        async for ev in adapter.events():
            events.append(ev)

        assert len(events) > 0
        for ev in events:
            assert ev.tenant_id == "tenant-alpha"
            assert ev.kind == "metric"
            assert ev.input_id is not None
            assert ev.event_time_utc.endswith("Z")

    asyncio.run(_test())


def test_organizer_adapter_parses_real_stream_and_tracks_unsupported(tmp_path: Path):
    """Verify parsing of confirmed stream and unsupported field tracking."""
    async def _test():
        stream_file = tmp_path / "organizer_sample.jsonl"
        sample_records = [
            {
                "id": "org-event-101",
                "host": "web-01",
                "timestamp": "2026-11-20T12:00:00.000Z",
                "cpu": 45.2,
                "memory": 60.1,
                "disk": True,
                "custom_organizer_tag": "experimental-tag",
            },
            {
                "invalid_json": True  # Missing timestamp
            }
        ]
        with open(stream_file, "w", encoding="utf-8") as f:
            for rec in sample_records:
                f.write(json.dumps(rec) + "\n")

        adapter = OrganizerAdapter(organizer_stream_path=stream_file, tenant_id="tenant-alpha")
        assert adapter.is_fallback is False
        assert adapter.mode == OrganizerAdapter.MODE_REAL

        events = []
        async for ev in adapter.events():
            events.append(ev)

        assert len(events) == 1
        assert events[0].input_id == "org-event-101"
        assert events[0].source_key == "tenant-alpha:web-01"
        assert events[0].metrics == {"cpu_pct": 45.2, "memory_pct": 60.1}

        status = adapter.get_status()
        assert status["malformed_count"] == 1
        assert "custom_organizer_tag" in status["unsupported_fields"]

    asyncio.run(_test())
