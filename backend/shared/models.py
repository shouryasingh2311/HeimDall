"""Wire models shared by the collector and SaaS."""

from datetime import datetime, timezone
import json
from typing import Annotated, Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Identifier = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9-]{0,63}$")]
Pseudonym = Annotated[str, Field(pattern=r"^src-[0-9a-f]{32}$")]
Percent = Annotated[float, Field(ge=0, le=100)]
Nonnegative = Annotated[float, Field(ge=0)]
UtcString = Annotated[
    str, Field(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$")
]
UuidString = Annotated[
    str, Field(pattern=r"^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$")
]
AnalysisStatus = Literal["live", "historical", "warming_up"]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False, hide_input_in_errors=True)


class Metrics(StrictModel):
    cpu_pct: Percent | None = None
    memory_pct: Percent | None = None
    disk_used_pct: Percent | None = None
    disk_read_bps: Nonnegative | None = None
    disk_write_bps: Nonnegative | None = None
    net_tx_bps: Nonnegative | None = None
    net_rx_bps: Nonnegative | None = None
    latency_ms: Nonnegative | None = None
    packet_loss_pct: Percent | None = None
    service_available: bool | None = None
    connectivity: bool | None = None

    @model_validator(mode="after")
    def has_signal(self) -> "Metrics":
        if all(value is None for value in self.model_dump().values()):
            raise ValueError("At least one metric is required")
        return self


class SecuritySummary(StrictModel):
    failed_attempts_count: Annotated[int, Field(ge=5)]
    window_seconds: Literal[10]
    risk_score: Percent
    attacker_id: Annotated[str, Field(pattern=r"^att-[0-9a-f]{32}$")]


class CollectorIdentity(StrictModel):
    schema_version: Literal[1]
    tenant_id: Identifier
    collector_id: Identifier
    region: Identifier
    source_timezone: Annotated[str, Field(min_length=1, max_length=64)]

    @field_validator("schema_version", mode="before")
    @classmethod
    def integer_literal(cls, value: object) -> object:
        if type(value) is not int:
            raise ValueError("Schema version must be an integer")
        return value

    @field_validator("source_timezone")
    @classmethod
    def known_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise ValueError("Expected IANA timezone") from error
        return value


class MetadataPayload(CollectorIdentity):
    policy_version: Literal["metadata-v1"]
    payload_uuid: UuidString
    source_id: Pseudonym
    event_time_utc: UtcString
    event_type: Literal["metric", "auth_threat"]
    metrics: Metrics | None
    security: SecuritySummary | None
    severity: Literal["info", "warning", "critical"]

    @field_validator("event_time_utc")
    @classmethod
    def valid_timestamp(cls, value: str) -> str:
        parse_utc(value)
        return value

    @field_validator("payload_uuid")
    @classmethod
    def stable_uuid(cls, value: str) -> str:
        if UUID(value).version != 5:
            raise ValueError("Expected UUIDv5")
        return value

    @model_validator(mode="after")
    def matching_variant(self) -> "MetadataPayload":
        if self.event_type == "metric":
            valid = self.metrics is not None and self.security is None
        else:
            valid = self.metrics is None and self.security is not None
        if not valid:
            raise ValueError("Payload does not match event type")
        return self


class CollectorHeartbeat(CollectorIdentity):
    heartbeat_uuid: UuidString
    generated_at_utc: UtcString
    version: Annotated[str, Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$", max_length=24)]
    rss_mb: Nonnegative
    cpu_pct: Percent
    queue_depth: Annotated[int, Field(ge=0)]
    config_status: Literal["valid", "invalid"]

    @field_validator("generated_at_utc")
    @classmethod
    def valid_timestamp(cls, value: str) -> str:
        parse_utc(value)
        return value


class IngestReceipt(StrictModel):
    payload_uuid: UuidString
    status: Literal["accepted", "duplicate"]
    body_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    received_at_utc: UtcString
    analysis_status: AnalysisStatus


class PayloadDetail(MetadataPayload):
    body_sha256: str
    received_at_utc: UtcString
    analysis_status: AnalysisStatus


def canonical_bytes(payload: BaseModel) -> bytes:
    return json.dumps(
        payload.model_dump(mode="json"),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
