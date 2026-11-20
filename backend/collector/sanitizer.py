"""Construct the allow-listed metric wire event from local input."""

import hashlib
import hmac
import json
from uuid import NAMESPACE_URL, uuid5

from backend.collector.demo_source import RawEvent
from backend.shared.config import CollectorSettings
from backend.shared.models import MetadataPayload, Metrics, SecuritySummary


def pseudonym(key_hex: str, local_source: str) -> str:
    return "src-" + hmac.new(bytes.fromhex(key_hex), local_source.encode(), hashlib.sha256).hexdigest()[:32]


class Sanitizer:
    def __init__(self, settings: CollectorSettings):
        self.settings = settings
        self.sources = {
            source: pseudonym(settings.hmac_key.get_secret_value(), source)
            for source in settings.source_keys
        }

    def source(self, event: RawEvent) -> str:
        config = self.settings
        if event.tenant_id != config.tenant_id or event.collector_id != config.collector_id:
            raise ValueError("Input identity does not match collector")
        source_id = self.sources.get(event.source_key)
        if source_id is None or not event.input_id:
            raise ValueError("Input source or event identity is unconfigured")
        return source_id

    def metric(self, event: RawEvent) -> MetadataPayload:
        if event.kind != "metric" or not isinstance(event.metrics, dict):
            raise ValueError("Invalid local metric event")

        approved = {key: value for key, value in event.metrics.items() if key in Metrics.model_fields}
        return self._payload(event, "metric", Metrics.model_validate(approved), None)

    def threat(self, event: RawEvent, attacker: str, count: int) -> MetadataPayload:
        summary = SecuritySummary(
            failed_attempts_count=count, window_seconds=10, risk_score=min(100, 18 * count), attacker_id=attacker,
        )
        return self._payload(event, "auth_threat", None, summary)

    def _payload(self, event, event_type, metrics, security):
        config = self.settings
        source_id = self.source(event)
        identity = json.dumps([config.tenant_id, config.collector_id, source_id, event.input_id, event_type])
        return MetadataPayload(
            schema_version=1,
            policy_version="metadata-v1",
            payload_uuid=str(uuid5(NAMESPACE_URL, identity)),
            tenant_id=config.tenant_id,
            collector_id=config.collector_id,
            source_id=source_id,
            region=config.region,
            event_time_utc=event.event_time_utc,
            source_timezone=event.source_timezone,
            event_type=event_type,
            metrics=metrics,
            security=security,
            severity="critical" if security else "info",
        )
