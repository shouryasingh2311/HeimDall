"""
Organizer Stream Adapter with Labelled Fallback.

Owned by Member 3 (feat/fixtures-validation).
Fulfills SIMU-01 and Check V00 per CONTRACTS.md and MEMBER_3_VALIDATION.md:
- Adapts real organizer telemetry stream/file into canonical RawEvents when available.
- Preserves external event identity and timestamps faithfully.
- If external organizer stream is unconfirmed/absent, operates in explicit labelled fallback
  mode (DEMO_FALLBACK) and records the gap honestly (never claiming false compatibility).
- Tracks unsupported fields and parsing diagnostics.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

from backend.collector.demo_source import DemoSource, RawEvent


class OrganizerAdapter:
    """
    Adapter for hackathon organizer telemetry feeds.
    Provides clear distinction between REAL_ORGANIZER mode and DEMO_FALLBACK mode.
    """

    MODE_REAL = "REAL_ORGANIZER"
    MODE_FALLBACK = "DEMO_FALLBACK"

    def __init__(
        self,
        organizer_stream_path: Optional[str | Path] = None,
        tenant_id: str = "tenant-alpha",
        collector_id: str = "collector-alpha-1",
    ):
        self.stream_path = Path(organizer_stream_path) if organizer_stream_path else None
        self.tenant_id = tenant_id
        self.collector_id = collector_id

        # Determine mode
        if self.stream_path and self.stream_path.exists():
            self.mode = self.MODE_REAL
            self.status_description = f"Ingesting confirmed organizer stream from {self.stream_path}"
        else:
            self.mode = self.MODE_FALLBACK
            self.status_description = "DEMO_FALLBACK: organizer stream unavailable; using deterministic demo data."

        self.unsupported_fields: List[str] = []
        self.malformed_count: int = 0
        self.records_processed: int = 0
        self._demo_fallback_source = DemoSource(seed=999) if self.mode == self.MODE_FALLBACK else None

    @property
    def is_fallback(self) -> bool:
        """True if operating in simulated fallback mode."""
        return self.mode == self.MODE_FALLBACK

    def get_status(self) -> Dict[str, Any]:
        """Diagnostic state required for Check V00."""
        return {
            "mode": self.mode,
            "is_fallback": self.is_fallback,
            "status_description": self.status_description,
            "stream_path": str(self.stream_path) if self.stream_path else None,
            "records_processed": self.records_processed,
            "malformed_count": self.malformed_count,
            "unsupported_fields": list(set(self.unsupported_fields)),
        }

    def _adapt_organizer_record(self, raw_dict: Dict[str, Any], record_idx: int) -> Optional[RawEvent]:
        """
        Map external organizer dictionary schema to canonical RawEvent.
        Expected organizer conventions (e.g. host/timestamp/metrics).
        """
        # Track any unmapped or unexpected fields
        recognized_keys = {
            "id", "uuid", "host", "hostname", "timestamp", "time", "metrics",
            "cpu", "memory", "disk", "network", "type", "message", "source"
        }
        for k in raw_dict.keys():
            if k not in recognized_keys:
                self.unsupported_fields.append(k)

        # Extract identifier
        raw_id = raw_dict.get("id") or raw_dict.get("uuid") or f"org-rec-{record_idx:06d}"
        source_name = raw_dict.get("host") or raw_dict.get("hostname") or raw_dict.get("source", "unknown-source")
        time_str = raw_dict.get("timestamp") or raw_dict.get("time")

        if not time_str:
            self.malformed_count += 1
            return None

        # Normalize metrics if nested or flat
        metrics_dict: Dict[str, Any] = {}
        if isinstance(raw_dict.get("metrics"), dict):
            metrics_dict = raw_dict["metrics"]
        else:
            # Map top-level candidates
            if "cpu" in raw_dict and isinstance(raw_dict["cpu"], (int, float)):
                metrics_dict["cpu_pct"] = float(raw_dict["cpu"])
            if "memory" in raw_dict and isinstance(raw_dict["memory"], (int, float)):
                metrics_dict["memory_pct"] = float(raw_dict["memory"])
            if "disk" in raw_dict and isinstance(raw_dict["disk"], (int, float)):
                metrics_dict["disk_used_pct"] = float(raw_dict["disk"])

        # Default connectivity if valid metrics exist
        if metrics_dict:
            metrics_dict.setdefault("connectivity", True)
            metrics_dict.setdefault("service_available", True)

        self.records_processed += 1
        return RawEvent(
            source_key=f"{self.tenant_id}:{source_name}",
            tenant_id=self.tenant_id,
            collector_id=self.collector_id,
            input_id=str(raw_id),
            event_time_utc=str(time_str),
            source_timezone="UTC",
            kind="metric",
            metrics=metrics_dict,
            raw_text=raw_dict.get("message") or json.dumps(raw_dict),
        )

    async def events(self) -> AsyncGenerator[RawEvent, None]:
        """
        Async generator yielding RawEvents from organizer stream or labelled fallback.
        """
        if self.mode == self.MODE_REAL and self.stream_path:
            with open(self.stream_path, "r", encoding="utf-8") as f:
                for idx, line in enumerate(f, start=1):
                    line_s = line.strip()
                    if not line_s:
                        continue
                    try:
                        record = json.loads(line_s)
                        event = self._adapt_organizer_record(record, idx)
                        if event:
                            yield event
                    except Exception:
                        self.malformed_count += 1
        else:
            # Labelled fallback using demo generator
            assert self._demo_fallback_source is not None
            # Generate a finite batch of fallback events for tenant
            batch = self._demo_fallback_source.generate_tick(tenants=[self.tenant_id])
            for event in batch:
                self.records_processed += 1
                yield event
