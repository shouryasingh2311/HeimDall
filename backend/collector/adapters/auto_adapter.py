"""
Universal Auto-Detecting Telemetry Ingestion Adapter.

Supports:
- JSONL (newline-delimited JSON)
- JSON (top-level array or envelope `{"records": [...]}` / `{"events": [...]}`)
- CSV and TSV (with header row)
- Gzip compressed versions (.gz) of all supported formats
- Live HTTP/HTTPS streaming or polling endpoint (--organizer-url)
- Configurable field mapping (--map mapping.yaml/json) with automatic alias guessing
- Timestamp parsing: ISO 8601, epoch seconds, epoch milliseconds
- Ratio-to-percentage normalization (0.0..1.0 -> 0..100%)
- Stable UUIDv5 event identities preventing duplicates on replay
- Strict local isolation: unmapped/unsupported fields never enter wire payload
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
import gzip
import io
import json
from pathlib import Path
import re
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple
import urllib.parse
from uuid import NAMESPACE_URL, uuid5

import httpx

from backend.collector.demo_source import RawEvent

# Heimdall canonical metric fields
CANONICAL_METRICS = {
    "cpu_pct", "memory_pct", "disk_used_pct", "disk_read_bps", "disk_write_bps",
    "net_tx_bps", "net_rx_bps", "latency_ms", "packet_loss_pct", "service_available", "connectivity"
}

PERCENT_FIELDS = {"cpu_pct", "memory_pct", "disk_used_pct", "packet_loss_pct"}

# Common aliases for automatic guessing without a mapping file
DEFAULT_ALIASES: Dict[str, List[str]] = {
    "timestamp": ["timestamp", "time", "ts", "@timestamp", "datetime", "date", "event_time", "event_time_utc", "created_at"],
    "host": ["host", "hostname", "node", "server", "machine", "instance", "device", "src", "source"],
    "cpu_pct": ["cpu_pct", "cpu", "cpu_usage", "cpu_percent", "cpu_utilization", "cpu_load"],
    "memory_pct": ["memory_pct", "memory", "mem", "mem_usage", "mem_percent", "mem_used_pct", "memory_usage"],
    "disk_used_pct": ["disk_used_pct", "disk", "disk_usage", "disk_used", "disk_percent", "disk_pct", "disk_utilization"],
    "latency_ms": ["latency_ms", "latency", "resp_time", "response_time", "rtt", "ping"],
    "packet_loss_pct": ["packet_loss_pct", "packet_loss", "loss", "pkt_loss", "drop_rate"],
    "net_tx_bps": ["net_tx_bps", "net_tx", "tx_bytes", "bytes_sent", "network_out"],
    "net_rx_bps": ["net_rx_bps", "net_rx", "rx_bytes", "bytes_recv", "network_in"],
    "auth_success": ["auth_success", "success", "status", "login_success", "authenticated"],
    "source_ip": ["source_ip", "ip", "client_ip", "remote_ip", "src_ip"],
    "username": ["username", "user", "login", "account", "usr"],
    "message": ["message", "raw_text", "msg", "log", "detail", "description"],
}


def load_mapping_file(map_path: str | Path | None) -> Dict[str, str]:
    """Load field mapping dictionary from JSON or YAML-like key-value file."""
    if not map_path:
        return {}
    p = Path(map_path)
    if not p.is_file():
        raise FileNotFoundError(f"Mapping file not found: {map_path}")

    content = p.read_text(encoding="utf-8").strip()
    if not content:
        return {}

    # Try JSON
    try:
        data = json.loads(content)
        if isinstance(data, dict):
            # Normalize to lower-case string mappings
            return {str(k).lower().strip(): str(v).strip() for k, v in data.items()}
    except json.JSONDecodeError:
        pass

    # Simple line-by-line YAML parser (key: value)
    result = {}
    for line in content.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and ":" in line:
            k, v = line.split(":", 1)
            result[k.strip().strip("'\"").lower()] = v.strip().strip("'\"")
    return result


def parse_timestamp_to_utc(val: Any) -> Optional[str]:
    """Parse ISO string, epoch seconds, or epoch milliseconds to ISO UTC string."""
    if val is None or val == "":
        return None

    # Epoch numbers (int or float)
    if isinstance(val, (int, float)):
        # Epoch milliseconds (> 1e11)
        if val > 1e11:
            dt = datetime.fromtimestamp(val / 1000.0, tz=timezone.utc)
        else:
            dt = datetime.fromtimestamp(float(val), tz=timezone.utc)
        return dt.isoformat(timespec="microseconds").replace("+00:00", "Z")

    val_str = str(val).strip()

    # Numeric string check (epoch in string)
    try:
        num = float(val_str)
        if num > 1e11:
            dt = datetime.fromtimestamp(num / 1000.0, tz=timezone.utc)
        elif num > 1e8:  # Epoch seconds after 1973
            dt = datetime.fromtimestamp(num, tz=timezone.utc)
            return dt.isoformat(timespec="microseconds").replace("+00:00", "Z")
    except ValueError:
        pass

    # ISO 8601 string parsing
    try:
        # Replace trailing Z with +00:00 for fromisoformat compatibility
        clean_iso = val_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean_iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt.isoformat(timespec="microseconds").replace("+00:00", "Z")
    except ValueError:
        pass

    # Try common formats
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y/%m/%d %H:%M:%S"):
        try:
            dt = datetime.strptime(val_str, fmt).replace(tzinfo=timezone.utc)
            return dt.isoformat(timespec="microseconds").replace("+00:00", "Z")
        except ValueError:
            pass

    return None


class AutoAdapter:
    """
    Intelligent adapter that inspects file or URL streams, auto-detects
    schema and formatting, and yields compliant RawEvent objects.
    """

    def __init__(
        self,
        source: Optional[str | Path] = None,
        url: Optional[str] = None,
        map_path: Optional[str | Path] = None,
        mapping: Optional[Dict[str, str]] = None,
        tenant_id: str = "tenant-alpha",
        collector_id: str = "collector-alpha-1",
        poll_interval_seconds: float = 2.0,
    ):
        self.source_path = Path(source) if source else None
        self.url = url
        self.tenant_id = tenant_id
        self.collector_id = collector_id
        self.poll_interval = poll_interval_seconds

        # Load explicit field mapping or use provided dict
        self.explicit_map = mapping or load_mapping_file(map_path)
        self.detected_format: Optional[str] = None
        self.chosen_mapping: Dict[str, str] = {}
        self.unmapped_fields: set[str] = set()
        self.malformed_count: int = 0
        self.total_records_read: int = 0
        self.valid_records_yielded: int = 0
        self.diagnostics: List[Dict[str, Any]] = []

    def detect_format(self, path: Optional[Path], header_bytes: bytes) -> str:
        """Detect format from extension first, then sniffing first bytes."""
        is_gz = False
        name = path.name.lower() if path else ""

        if name.endswith(".gz") or header_bytes.startswith(b"\x1f\x8b"):
            is_gz = True
            if header_bytes.startswith(b"\x1f\x8b"):
                try:
                    header_bytes = gzip.decompress(header_bytes[:8192])
                except Exception:
                    pass

        suffix = name[:-3] if name.endswith(".gz") else name

        if suffix.endswith(".jsonl") or suffix.endswith(".ndjson"):
            return "jsonl.gz" if is_gz else "jsonl"
        if suffix.endswith(".json"):
            return "json.gz" if is_gz else "json"
        if suffix.endswith(".csv"):
            return "csv.gz" if is_gz else "csv"
        if suffix.endswith(".tsv"):
            return "tsv.gz" if is_gz else "tsv"

        # Sniff content
        text_preview = header_bytes.decode("utf-8", errors="ignore").strip()
        if not text_preview:
            return "unknown"

        if text_preview.startswith("[") or text_preview.startswith("{\n  \"records\"") or text_preview.startswith("{\"records\""):
            return "json.gz" if is_gz else "json"

        # Check if first line parses as JSON dict
        first_line = text_preview.splitlines()[0].strip()
        if first_line.startswith("{") and first_line.endswith("}"):
            try:
                parsed = json.loads(first_line)
                if isinstance(parsed, dict):
                    return "jsonl.gz" if is_gz else "jsonl"
            except Exception:
                pass

        # Check delimiter for CSV / TSV
        if "\t" in first_line and len(first_line.split("\t")) > 1:
            return "tsv.gz" if is_gz else "tsv"
        if "," in first_line and len(first_line.split(",")) > 1:
            return "csv.gz" if is_gz else "csv"

        return "jsonl.gz" if is_gz else "jsonl"

    def _build_field_mapping(self, sample_keys: List[str]) -> Dict[str, str]:
        """Construct the resolved mapping between raw input keys and canonical target keys."""
        resolved: Dict[str, str] = dict(self.chosen_mapping)
        sample_keys_lower = {k.lower(): k for k in sample_keys}

        # 1. Apply explicit mapping first
        for organizer_k, target_k in self.explicit_map.items():
            k_low = organizer_k.lower()
            if k_low in sample_keys_lower:
                resolved[sample_keys_lower[k_low]] = target_k

        # 2. For unmapped input fields, guess canonical field using common aliases
        for orig_k in sample_keys:
            if orig_k in resolved:
                continue
            k_clean = re.sub(r"[_\-\.]", "", orig_k.lower())
            for canonical, aliases in DEFAULT_ALIASES.items():
                for alias in aliases:
                    a_clean = re.sub(r"[_\-\.]", "", alias.lower())
                    if k_clean == a_clean:
                        resolved[orig_k] = canonical
                        break
                if orig_k in resolved:
                    break

        return resolved

    def _normalize_record(self, raw_dict: Dict[str, Any], record_idx: int) -> Optional[RawEvent]:
        """Convert a raw dictionary into a canonical RawEvent with type and ratio conversions."""
        self.total_records_read += 1

        unseen_keys = [k for k in raw_dict.keys() if k not in self.chosen_mapping and k not in self.unmapped_fields]
        if unseen_keys:
            self.chosen_mapping = self._build_field_mapping(list(raw_dict.keys()))

        mapped: Dict[str, Any] = {}
        for raw_k, raw_v in raw_dict.items():
            target_k = self.chosen_mapping.get(raw_k)
            if target_k:
                mapped[target_k] = raw_v
            else:
                self.unmapped_fields.add(raw_k)

        # 1. Timestamp extraction & conversion
        raw_ts = (
            raw_dict.get("event_time_utc")
            or mapped.get("timestamp")
            or raw_dict.get("timestamp")
            or raw_dict.get("time")
            or raw_dict.get("ts")
            or raw_dict.get("event_time")
        )
        utc_ts = parse_timestamp_to_utc(raw_ts)
        if not utc_ts:
            self.malformed_count += 1
            self.diagnostics.append({
                "record_idx": record_idx,
                "error": "invalid_or_missing_timestamp",
                "raw_value": str(raw_ts),
            })
            return None

        # 2. Host / Source identification
        tenant_id = str(raw_dict.get("tenant_id") or self.tenant_id)
        collector_id = str(raw_dict.get("collector_id") or self.collector_id)
        source_timezone = str(raw_dict.get("source_timezone") or "UTC")

        if raw_dict.get("source_key"):
            source_key = str(raw_dict["source_key"])
        else:
            raw_host = (
                mapped.get("host") or raw_dict.get("host") or raw_dict.get("node")
                or raw_dict.get("hostname") or raw_dict.get("source") or "api-01"
            )
            source_name = str(raw_host).strip()
            # Normalization: if hostname contains prefix like "tenant-alpha:api-01", strip tenant prefix
            if ":" in source_name:
                source_name = source_name.split(":", 1)[1]
            source_key = f"{tenant_id}:{source_name}"

        # 3. Input ID generation (ensuring stable ID for replay deduplication)
        raw_id = (
            raw_dict.get("input_id")
            or mapped.get("id")
            or raw_dict.get("id")
            or raw_dict.get("uuid")
            or raw_dict.get("event_id")
        )
        if raw_id:
            input_id = str(raw_id)
        else:
            # Deterministic UUIDv5 across tenant, source, timestamp, and index
            input_id = str(uuid5(NAMESPACE_URL, f"{tenant_id}:{source_key}:{utc_ts}:{record_idx}"))

        # 4. Metric parsing & 0-1 ratio normalization
        metrics_dict: Dict[str, Any] = {}
        # Also handle nested "metrics" object if present
        nested_metrics = raw_dict.get("metrics")
        if isinstance(nested_metrics, dict):
            for k, v in nested_metrics.items():
                target_k = self.explicit_map.get(k.lower()) or k
                if target_k in CANONICAL_METRICS:
                    mapped[target_k] = v

        for target_metric in CANONICAL_METRICS:
            if target_metric in mapped:
                val = mapped[target_metric]
                if val is not None and val != "":
                    if target_metric in ("service_available", "connectivity"):
                        if isinstance(val, bool):
                            metrics_dict[target_metric] = val
                        elif isinstance(val, str):
                            metrics_dict[target_metric] = val.lower() in ("true", "1", "yes")
                        elif isinstance(val, (int, float)):
                            metrics_dict[target_metric] = bool(val)
                    else:
                        try:
                            num_val = float(val)
                            # Ratio normalization: if percentage field has 0 < val <= 1.0, scale to 0..100%
                            if target_metric in PERCENT_FIELDS and 0.0 < num_val <= 1.0:
                                num_val = round(num_val * 100.0, 2)
                            metrics_dict[target_metric] = num_val
                        except (ValueError, TypeError):
                            pass

        # 5. Auth / Security kind detection
        explicit_kind = raw_dict.get("kind")
        if explicit_kind:
            is_auth = (explicit_kind == "auth")
        else:
            is_auth = (mapped.get("auth_success") is not None)

        auth_success = None
        if is_auth:
            raw_succ = mapped.get("auth_success", raw_dict.get("auth_success"))
            if isinstance(raw_succ, bool):
                auth_success = raw_succ
            elif isinstance(raw_succ, str):
                auth_success = raw_succ.lower() in ("true", "1", "yes", "success", "ok")
            elif isinstance(raw_succ, (int, float)):
                auth_success = bool(raw_succ)

        source_ip = str(mapped["source_ip"]) if "source_ip" in mapped and mapped["source_ip"] else raw_dict.get("source_ip")
        username = str(mapped["username"]) if "username" in mapped and mapped["username"] else raw_dict.get("username")
        raw_text = str(raw_dict.get("raw_text") or mapped.get("message") or raw_dict.get("message") or json.dumps(raw_dict))

        event = RawEvent(
            source_key=source_key,
            tenant_id=tenant_id,
            collector_id=collector_id,
            input_id=input_id,
            event_time_utc=utc_ts,
            source_timezone=source_timezone,
            kind="auth" if is_auth else "metric",
            metrics=metrics_dict if not is_auth else None,
            raw_text=raw_text,
            source_ip=source_ip,
            username=username,
            auth_success=auth_success,
        )
        self.valid_records_yielded += 1
        return event

    def _open_stream(self) -> Tuple[io.TextIOBase, str]:
        """Open local file or decompress gzip stream and detect format."""
        if not self.source_path or not self.source_path.exists():
            raise FileNotFoundError(f"Source file not found: {self.source_path}")

        raw_bytes = self.source_path.read_bytes()
        if not raw_bytes:
            raise ValueError(f"Source file is empty: {self.source_path}")

        fmt = self.detect_format(self.source_path, raw_bytes)
        self.detected_format = fmt

        if fmt.endswith(".gz") or raw_bytes.startswith(b"\x1f\x8b"):
            decompressed = gzip.decompress(raw_bytes)
            stream = io.StringIO(decompressed.decode("utf-8", errors="replace"))
        else:
            stream = io.StringIO(raw_bytes.decode("utf-8", errors="replace"))

        return stream, fmt

    async def events(self) -> AsyncGenerator[RawEvent, None]:
        """Async generator yielding compliant RawEvents from file or live URL."""
        if self.url:
            async for ev in self._events_from_url():
                yield ev
            return

        stream, fmt = self._open_stream()
        clean_fmt = fmt.replace(".gz", "")

        if clean_fmt == "json":
            # Top-level array or envelope
            content = stream.read().strip()
            if not content:
                return
            data = json.loads(content)
            records = data if isinstance(data, list) else data.get("records") or data.get("events") or data.get("data") or []
            for idx, item in enumerate(records, start=1):
                if isinstance(item, dict):
                    event = self._normalize_record(item, idx)
                    if event:
                        yield event
                else:
                    self.malformed_count += 1
        elif clean_fmt in ("csv", "tsv"):
            delimiter = "\t" if clean_fmt == "tsv" else ","
            reader = csv.DictReader(stream, delimiter=delimiter)
            for idx, row in enumerate(reader, start=1):
                event = self._normalize_record(row, idx)
                if event:
                    yield event
        else:
            # JSONL / NDJSON
            for idx, line in enumerate(stream, start=1):
                line_s = line.strip()
                if not line_s or line_s.startswith("#"):
                    continue
                try:
                    record = json.loads(line_s)
                    if isinstance(record, dict):
                        event = self._normalize_record(record, idx)
                        if event:
                            yield event
                    else:
                        self.malformed_count += 1
                except Exception:
                    self.malformed_count += 1

    async def _events_from_url(self) -> AsyncGenerator[RawEvent, None]:
        """Poll or stream from an external HTTP/HTTPS organizer endpoint."""
        assert self.url is not None
        seen_ids = set()
        record_idx = 0

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # Check for streaming response
                async with client.stream("GET", self.url) as response:
                    response.raise_for_status()
                    is_streaming = "chunked" in response.headers.get("transfer-encoding", "").lower() or "event-stream" in response.headers.get("content-type", "").lower()
                    if is_streaming:
                        async for line in response.aiter_lines():
                            line_s = line.strip()
                            if not line_s:
                                continue
                            try:
                                record = json.loads(line_s)
                                record_idx += 1
                                ev = self._normalize_record(record, record_idx)
                                if ev and ev.input_id not in seen_ids:
                                    seen_ids.add(ev.input_id)
                                    yield ev
                            except Exception:
                                self.malformed_count += 1
                        return
            except Exception:
                pass

            # Fallback to polling
            try:
                resp = await client.get(self.url)
                resp.raise_for_status()
                text = resp.text.strip()
                if text.startswith("[") or "records" in text:
                    data = resp.json()
                    records = data if isinstance(data, list) else data.get("records") or []
                    for item in records:
                        record_idx += 1
                        ev = self._normalize_record(item, record_idx)
                        if ev and ev.input_id not in seen_ids:
                            seen_ids.add(ev.input_id)
                            yield ev
                else:
                    for line in text.splitlines():
                        line_s = line.strip()
                        if not line_s:
                            continue
                        try:
                            record = json.loads(line_s)
                            record_idx += 1
                            ev = self._normalize_record(record, record_idx)
                            if ev and ev.input_id not in seen_ids:
                                seen_ids.add(ev.input_id)
                                yield ev
                        except Exception:
                            self.malformed_count += 1
            except Exception as e:
                self.diagnostics.append({"error": "url_fetch_failed", "url": self.url, "detail": str(e)})
