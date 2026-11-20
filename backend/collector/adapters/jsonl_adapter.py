"""
JSONL RawEvent Adapter.

Owned by Member 3 (feat/fixtures-validation).
Fulfills Phase 1 requirements per CONTRACTS.md and MEMBER_3_VALIDATION.md:
- Reads newline-delimited JSON files or streams.
- Converts valid records into canonical RawEvent instances.
- Preserves event identity, original timestamps, and timezone context.
- Records and exposes malformed record counts and parsing diagnostics.
- Never sends raw records over network; yields locally to collector pipeline.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

from backend.collector.demo_source import RawEvent


class JSONLAdapter:
    """
    Adapter that reads raw events from JSONL files.
    """

    def __init__(self, file_path: str | Path):
        self.file_path = Path(file_path)
        self.total_lines_read: int = 0
        self.valid_records_yielded: int = 0
        self.malformed_count: int = 0
        self.diagnostics: List[Dict[str, Any]] = []

    def get_stats(self) -> Dict[str, Any]:
        """Return parsing statistics for diagnostic reporting."""
        return {
            "file_path": str(self.file_path),
            "total_lines_read": self.total_lines_read,
            "valid_records_yielded": self.valid_records_yielded,
            "malformed_count": self.malformed_count,
            "diagnostics": list(self.diagnostics),
        }

    def _parse_line(self, line: str, line_number: int) -> Optional[RawEvent]:
        """Validate and parse a single line into a RawEvent."""
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            return None

        try:
            payload = json.loads(stripped)
        except Exception as exc:
            self.malformed_count += 1
            self.diagnostics.append({
                "line_number": line_number,
                "error": "json_decode_error",
                "detail": str(exc),
            })
            return None

        if not isinstance(payload, dict):
            self.malformed_count += 1
            self.diagnostics.append({
                "line_number": line_number,
                "error": "invalid_type",
                "detail": f"Expected JSON object, got {type(payload).__name__}",
            })
            return None

        # Check required fields
        required_keys = ["source_key", "tenant_id", "collector_id", "input_id", "event_time_utc"]
        missing = [k for k in required_keys if k not in payload]
        if missing:
            self.malformed_count += 1
            self.diagnostics.append({
                "line_number": line_number,
                "error": "missing_required_keys",
                "missing_keys": missing,
            })
            return None

        # Construct RawEvent
        kind = payload.get("kind", "metric")
        metrics = payload.get("metrics")
        if kind == "metric" and not isinstance(metrics, dict):
            self.malformed_count += 1
            self.diagnostics.append({
                "line_number": line_number,
                "error": "invalid_metrics",
                "detail": "Metric event must have a dictionary for 'metrics'",
            })
            return None

        event = RawEvent(
            source_key=str(payload["source_key"]),
            tenant_id=str(payload["tenant_id"]),
            collector_id=str(payload["collector_id"]),
            input_id=str(payload["input_id"]),
            event_time_utc=str(payload["event_time_utc"]),
            source_timezone=str(payload.get("source_timezone", "UTC")),
            kind=kind,
            metrics=metrics,
            raw_text=payload.get("raw_text"),
            source_ip=payload.get("source_ip"),
            username=payload.get("username"),
            auth_success=payload.get("auth_success"),
        )
        self.valid_records_yielded += 1
        return event

    async def events(self) -> AsyncGenerator[RawEvent, None]:
        """
        Async generator yielding RawEvents from the file.
        Matches CONTRACTS.md adapter specification.
        """
        if not self.file_path.exists():
            self.diagnostics.append({
                "error": "file_not_found",
                "path": str(self.file_path),
            })
            return

        with open(self.file_path, "r", encoding="utf-8") as f:
            for line_idx, line in enumerate(f, start=1):
                self.total_lines_read += 1
                parsed = self._parse_line(line, line_idx)
                if parsed is not None:
                    yield parsed
