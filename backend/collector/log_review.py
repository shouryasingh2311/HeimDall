"""Replay the shared import adapter's records with isolated detector state."""

from collections import Counter
import aiosqlite
from starlette.concurrency import run_in_threadpool

from backend.collector.adapters.auto_adapter import MAX_RECORDS, AutoAdapter, parse_records
from backend.collector.buffer_queue import SCHEMA as OUTBOX_SCHEMA
from backend.collector.demo_source import RawEvent
from backend.collector.sanitizer import Sanitizer
from backend.collector.security_analyzer import SCHEMA as AUTH_SCHEMA, SecurityAnalyzer
from backend.saas.detector import evaluate_metrics
from backend.shared.config import CollectorSettings, HealthPolicy
from backend.shared.models import parse_utc

async def analyze_log(body: bytes, settings: CollectorSettings, policy: HealthPolicy) -> dict:
    format_name, records, malformed = await run_in_threadpool(parse_records, body, AutoAdapter(tenant_id=settings.tenant_id, collector_id=settings.collector_id))
    sources = list(dict.fromkeys(record.source for _, record in records))
    sanitizer = Sanitizer(settings.model_copy(update={"source_keys": sources}))
    levels = Counter()
    counts = Counter(metrics_analyzed=0, auth_analyzed=0, auth_failures=0,
                     missing_timestamp=0, invalid_signals=0, unclassified=0, duplicate_metrics=0)
    baselines = {}
    findings = []
    metric_ids = set()
    async with aiosqlite.connect(":memory:") as db:
        await db.executescript(OUTBOX_SCHEMA + AUTH_SCHEMA)
        security = SecurityAnalyzer(db, MAX_RECORDS, sanitizer)
        for index, record in sorted(records, key=lambda item: item[1].timestamp or ""):
            if record.level:
                levels[record.level] += 1
            if record.auth_success is False:
                counts["auth_failures"] += 1
            if not (record.level or record.metrics or record.auth_success is not None):
                counts["unclassified"] += 1
            if not record.timestamp:
                counts["missing_timestamp"] += 1
                continue
            identity = f"id:{record.input_id}" if record.input_id is not None else f"row:{index}"
            event = RawEvent(record.source, settings.tenant_id, settings.collector_id, identity, record.timestamp)
            context = {"record": index, "source_id": sanitizer.source(event), "event_time_utc": record.timestamp}
            if record.metrics:
                event.metrics = record.metrics
                try:
                    payload = sanitizer.metric(event)
                except ValueError:
                    counts["invalid_signals"] += 1
                else:
                    if payload.payload_uuid in metric_ids:
                        counts["duplicate_metrics"] += 1
                    else:
                        metric_ids.add(payload.payload_uuid)
                        counts["metrics_analyzed"] += 1
                        signals, _, _ = evaluate_metrics(payload, policy, baselines.setdefault(payload.source_id, {}),
                                                         record.timestamp)
                        for signal in signals:
                            findings.append({**context, "type": "metric_anomaly", **vars(signal)})
            if record.auth_success is not None:
                event.kind, event.auth_success, event.source_ip = "auth", record.auth_success, record.source_ip
                try:
                    summary = await security.submit(event, parse_utc(record.timestamp))
                except (ValueError, OverflowError):
                    counts["invalid_signals"] += 1
                else:
                    counts["auth_analyzed"] += 1
                    if summary is not None:
                        payload, _ = summary
                        findings.append({**context, "type": "auth_threat", "severity": payload.severity,
                                         **payload.security.model_dump(mode="json")})
    return {"schema_version": 1, "mode": "local_replay", "format": format_name,
            "records": {"total": len(records) + malformed, "parsed": len(records), "malformed": malformed, **counts},
            "log_levels": dict(levels), "finding_count": len(findings), "findings": findings}
