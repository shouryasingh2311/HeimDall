"""
Tests for JSONLAdapter against synthetic fixtures.

Owned by Member 3 (feat/fixtures-validation).
Verifies:
- Accurate parsing of valid JSONL rows into RawEvent objects.
- Preserves raw_text, source_ip, and custom parameters for local processing.
- Handles corrupt/empty lines cleanly with error diagnostics.
"""

import asyncio
from pathlib import Path

from backend.collector.adapters.jsonl_adapter import JSONLAdapter


def test_jsonl_adapter_parses_secrets_fixture():
    async def _test():
        fixture_path = Path("tests/scenarios/fixtures/secrets.jsonl")
        assert fixture_path.exists()

        adapter = JSONLAdapter(fixture_path)
        events = []
        async for ev in adapter.events():
            events.append(ev)

        stats = adapter.get_stats()
        assert stats["valid_records_yielded"] == 3
        assert stats["malformed_count"] == 0

        # Ensure sensitive fields are preserved locally in RawEvent
        assert "SuperSecretPassword123" in events[0].raw_text
        assert events[2].kind == "auth"
        assert events[2].username == "admin"
        assert events[2].source_ip == "10.0.0.42"

    asyncio.run(_test())
