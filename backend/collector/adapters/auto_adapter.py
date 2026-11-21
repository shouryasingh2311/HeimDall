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
from dataclasses import dataclass
from itertools import chain
import math
import zlib
from backend.shared.models import Metrics
from datetime import datetime, timezone
import gzip
import io
import json
from pathlib import Path
import re
from typing import Any, AsyncGenerator, Dict, List, Optional
from uuid import NAMESPACE_URL, uuid5

import httpx

from backend.collector.demo_source import RawEvent

# Heimdall canonical metric fields
CANONICAL_METRICS = set(Metrics.model_fields)

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


def parse_boolean(value):
    if isinstance(value, bool):
        return value
    if type(value) in (int, float):
        return {0: False, 1: True}.get(value)
    if isinstance(value, str):
        return {"true": True, "1": True, "yes": True, "success": True, "ok": True,
                "false": False, "0": False, "no": False, "failure": False, "failed": False}.get(value.lower().strip())
    return None


def parse_timestamp_to_utc(val: Any) -> Optional[str]:
    """Normalize finite epoch values and ISO timestamps without guessing dates."""
    if val is None or isinstance(val, bool) or val == "":
        return None
    try:
        number = float(val)
    except (TypeError, ValueError):
        number = None
    if number is not None:
        if not math.isfinite(number):
            return None
        try:
            dt = datetime.fromtimestamp(number / 1000 if abs(number) >= 1e11 else number, timezone.utc)
            return dt.isoformat(timespec="microseconds").replace("+00:00", "Z")
        except (ValueError, OverflowError, OSError):
            return None
    try:
        dt = datetime.fromisoformat(str(val).strip().replace("Z", "+00:00"))
    except ValueError:
        try:
            dt = datetime.strptime(str(val), "%Y/%m/%d %H:%M:%S")
        except ValueError:
            return None
    dt = dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
    return dt.isoformat(timespec="microseconds").replace("+00:00", "Z")


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
        """Detect content independently of the filename."""
        fmt, _ = detect_records(decode_log(header_bytes), self.explicit_map)
        return fmt + (".gz" if header_bytes.startswith(b"\x1f\x8b") else "")

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
            if orig_k in CANONICAL_METRICS:
                resolved[orig_k] = orig_k
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
            if source_name.startswith(f"{tenant_id}:"):
                source_name = source_name[len(tenant_id) + 1:]
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
                            metrics_dict[target_metric] = parse_boolean(val)
                        elif isinstance(val, (int, float)):
                            metrics_dict[target_metric] = parse_boolean(val)
                    else:
                        try:
                            num_val = float(val)
                            # Ratio normalization: if percentage field has 0 < val <= 1.0, scale to 0..100%
                            if (target_metric in PERCENT_FIELDS and 0.0 < num_val <= 1.0
                                    and target_metric not in raw_dict
                                    and not (isinstance(nested_metrics, dict) and target_metric in nested_metrics)):
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
                auth_success = parse_boolean(raw_succ)
            elif isinstance(raw_succ, (int, float)):
                auth_success = parse_boolean(raw_succ)

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

    async def events(self) -> AsyncGenerator[RawEvent, None]:
        """Async generator yielding compliant RawEvents from file or live URL."""
        if self.url:
            async for ev in self._events_from_url():
                yield ev
            return

        if self.source_path is None:
            raise FileNotFoundError("No input file supplied")
        with self.source_path.open("rb") as stream:
            body = stream.read(MAX_FILE_BYTES + 1)
        self.malformed_count = 0
        fmt, records, malformed = parse_records(body, self)
        self.detected_format = fmt + (".gz" if body.startswith(b"\x1f\x8b") else "")
        self.malformed_count += malformed
        for index, record in records:
            event = record.event
            if event is None and record.timestamp:
                event = self._normalize_record({
                    "timestamp": record.timestamp, "host": record.source,
                    "auth_success": record.auth_success, "source_ip": record.source_ip,
                    "metrics": record.metrics or {},
                }, index)
            if event:
                yield event

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


MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_RECORDS = 10_000
LEVELS = {"trace": "debug", "debug": "debug", "info": "info", "notice": "info",
          "warn": "warning", "warning": "warning", "err": "error", "error": "error",
          "critical": "critical", "crit": "critical", "fatal": "critical", "alert": "critical",
          "panic": "critical", "emerg": "critical"}
SYSLOG_LEVELS = ("critical", "critical", "critical", "error", "warning", "info", "info", "debug")
TIMESTAMP = re.compile(r"^\d{4}-\d\d-\d\d[T ]\d\d:\d\d:\d\d(?:[.,]\d{1,6})?(?:Z|[+-]\d\d:?\d\d)?")
SYSLOG_HEADER = re.compile(r"^<(\d{1,3})>\d+\s+(\S+)\s+(\S+)")
SYSLOG_PRIORITY = re.compile(r"^<(\d{1,3})>")
TEXT_LEVEL = re.compile(r"^\s*\[?([a-z]+)\b[\]:\s]", re.IGNORECASE)
HTTP_ACCESS = re.compile(r'"[A-Z]+ [^"\r\n]* HTTP/\d(?:\.\d)?"\s+([1-5]\d\d)\s')
SSH_FAILURE = re.compile(r"\bFailed (?:password|publickey)\b", re.IGNORECASE)
SSH_ORIGIN = re.compile(r"\bfrom\s+([\da-f:.]+)(?=\s|$)", re.IGNORECASE)
ALIASES = {"cpu": "cpu_pct", "memory": "memory_pct", "disk": "disk_used_pct"}
FIELD_NAMES = set(Metrics.model_fields) | ALIASES.keys() | {
    "timestamp", "event_time_utc", "time", "@timestamp", "level", "severity", "loglevel", "log_level",
    "message", "msg", "raw_text", "source_ip", "auth_success", "host", "hostname", "source", "source_key",
}


class LogImportError(ValueError):
    pass


@dataclass
class LogRecord:
    timestamp: str | None
    source: str
    level: str | None = None
    metrics: dict | None = None
    auth_success: bool | None = None
    source_ip: str | None = None
    input_id: str | None = None
    event: RawEvent | None = None


def decode_log(body: bytes) -> str:
    if len(body) > MAX_FILE_BYTES:
        raise LogImportError("The file must be at most 5 MiB.")
    if body.startswith(b"\x1f\x8b"):
        try:
            with gzip.GzipFile(fileobj=io.BytesIO(body)) as archive:
                body = archive.read(MAX_FILE_BYTES + 1)
        except (OSError, EOFError, zlib.error):
            raise LogImportError("This gzip file could not be read.") from None
    if len(body) > MAX_FILE_BYTES:
        raise LogImportError("The uncompressed log must be at most 5 MiB.")
    try:
        encoding = "utf-16" if body.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
        content = body.decode(encoding)
    except UnicodeError:
        raise LogImportError("Export binary logs as text, JSON, JSONL, CSV, or TSV first.") from None
    if any(ord(character) < 32 and character not in "\r\n\t" for character in content):
        raise LogImportError("Export binary logs as text, JSON, JSONL, CSV, or TSV first.")
    if not content.strip():
        raise LogImportError("The file has no log records.")
    return content


def detect_records(content: str, mapping=None):
    first = content.lstrip()
    if first.startswith(("{", "[")):
        try:
            document = json.loads(content)
        except (ValueError, RecursionError):
            pass
        else:
            if isinstance(document, dict):
                for key in ("logs", "events", "records", "entries", "data"):
                    if isinstance(document.get(key), list):
                        return "json", document[key]
                return "json", [document]
            return "json", document

    adapter_fields = set(mapping or {}) | {alias.lower() for aliases in DEFAULT_ALIASES.values() for alias in aliases}
    lines = (line.strip() for line in io.StringIO(content) if line.strip() and not line.lstrip().startswith("#"))
    header = next(lines, "")
    if not header:
        raise LogImportError("The file has no log records.")
    for delimiter, name in ((",", "csv"), ("\t", "tsv")):
        if delimiter in header:
            columns = next(csv.reader([header], delimiter=delimiter))
            if any(column.strip().lower() in FIELD_NAMES or column.strip().lower() in adapter_fields for column in columns):
                return name, delimited_records(first, delimiter)
    return ("jsonl" if header.startswith("{") else "text"), chain((header,), lines)


def delimited_records(content: str, delimiter: str):
    reader = csv.DictReader(io.StringIO(content, newline=""), delimiter=delimiter, strict=True)
    columns = [column.strip().lower() for column in reader.fieldnames or []]
    if len(columns) != len(set(columns)):
        raise LogImportError("The log has duplicate column names.")
    reader.fieldnames = columns
    yield from reader


def text_record(line: str) -> LogRecord:
    priority = SYSLOG_PRIORITY.match(line)
    syslog_level = SYSLOG_LEVELS[int(priority[1]) % 8] if priority and int(priority[1]) <= 191 else None
    header = SYSLOG_HEADER.match(line)
    if header:
        return LogRecord(parse_timestamp_to_utc(header[2]), header[3], syslog_level)
    timestamp = TIMESTAMP.match(line)
    message = line[timestamp.end():].lstrip(" \t:-") if timestamp else line
    token = TEXT_LEVEL.match(message)
    level = syslog_level or (LEVELS.get(token[1].lower()) if token else None)
    if level is None and (access := HTTP_ACCESS.search(message[:8192])):
        level = {"4": "warning", "5": "error"}.get(access[1][0], "info")
    return LogRecord(parse_timestamp_to_utc(timestamp[0]) if timestamp else None, "imported-log",
                     level)


def read_record(value, format_name: str, adapter, index: int) -> LogRecord | None:
    if format_name in ("jsonl", "text") and (format_name == "jsonl" or value.startswith("{")):
        try:
            value = json.loads(value)
        except (ValueError, RecursionError):
            return None
    if isinstance(value, str):
        record, message = text_record(value), value
    elif isinstance(value, dict) and value and None not in value:
        get = value.get
        message = next((get(key) for key in ("message", "msg", "raw_text") if isinstance(get(key), str)), "")
        record = text_record(message)
        record.level = next((LEVELS[get(key).strip().lower()] for key in ("level", "severity", "loglevel", "log_level")
                             if isinstance(get(key), str) and get(key).strip().lower() in LEVELS), record.level)
        normalized = adapter._normalize_record(value, index)
        if normalized:
            record.timestamp = normalized.event_time_utc
            record.source = normalized.source_key
            record.metrics = normalized.metrics
            record.auth_success = normalized.auth_success
            record.source_ip = normalized.source_ip
            record.input_id = normalized.input_id
            record.event = normalized
    else:
        return None
    message = message[:8192]
    if record.auth_success is None and (failure := SSH_FAILURE.search(message)):
        record.auth_success = False
        origin = SSH_ORIGIN.search(message, failure.end())
        record.source_ip = origin[1] if origin else None
    if record.event is not None and record.auth_success is not None:
        record.event.kind = "auth"
        record.event.auth_success = record.auth_success
        record.event.source_ip = record.source_ip
    try:
        record.source.encode("utf-8")
        if record.input_id is not None:
            record.input_id.encode("utf-8")
    except UnicodeError:
        return None
    return record


def parse_records(body: bytes, adapter=None) -> tuple[str, list[tuple[int, LogRecord]], int]:
    adapter = adapter or AutoAdapter()
    records = []
    malformed = 0
    try:
        format_name, values = detect_records(decode_log(body), adapter.explicit_map)
        for index, value in enumerate(values, 1):
            if index > MAX_RECORDS:
                raise LogImportError("The file must have at most 10,000 records.")
            record = read_record(value, format_name, adapter, index)
            if record is None:
                malformed += 1
            else:
                records.append((index, record))
    except csv.Error:
        raise LogImportError("The delimited log could not be parsed. Check its quoting and field sizes.") from None
    if not records and not malformed:
        raise LogImportError("The file has no log records.")
    return format_name, records, malformed
