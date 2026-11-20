"""Configuration shapes. Collector source keys remain in collector config."""

from pathlib import Path
from typing import Annotated, Literal, TypeVar

from pydantic import Field, SecretStr, field_validator, model_validator

from backend.shared.models import Identifier, Metrics, Pseudonym, StrictModel

TokenDigest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Model = TypeVar("Model", bound=StrictModel)


class Credential(StrictModel):
    role: Literal["collector", "operator"]
    tenant_id: Identifier
    region: Identifier
    token_sha256: TokenDigest
    collector_id: Identifier | None = None
    source_ids: list[Pseudonym] = Field(default_factory=list)

    @model_validator(mode="after")
    def scope_matches_role(self) -> "Credential":
        if self.role == "collector" and (self.collector_id is None or not self.source_ids):
            raise ValueError("Collector membership is required")
        if self.role == "operator" and (self.collector_id is not None or self.source_ids):
            raise ValueError("Operator scope is tenant-level")
        return self


class HealthPolicy(StrictModel):
    cpu: list[float] = Field(default_factory=lambda: [70., 85., 95.])
    memory: list[float] = Field(default_factory=lambda: [70., 85., 95.])
    disk: list[float] = Field(default_factory=lambda: [75., 90., 98.])
    latency: list[float] = Field(default_factory=lambda: [50., 120., 500.])
    packet_loss: list[float] = Field(default_factory=lambda: [0., 2., 10.])
    risk: list[float] = Field(default_factory=lambda: [50., 90.])
    expected_signals: dict[Pseudonym, list[str]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_rules(self):
        for name in ("cpu", "memory", "disk", "latency", "packet_loss", "risk"):
            values = getattr(self, name)
            if len(values) != (2 if name == "risk" else 3) or values != sorted(set(values)) or values[0] < 0:
                raise ValueError("Expected strictly increasing health thresholds")
        if any(set(fields) - Metrics.model_fields.keys() for fields in self.expected_signals.values()):
            raise ValueError("Unknown expected metric")
        return self


class ServerSettings(StrictModel):
    credentials: Annotated[list[Credential], Field(min_length=1)]
    dev_origin: Literal["http://localhost:5173", "http://127.0.0.1:5173"] | None = None
    health: HealthPolicy = Field(default_factory=HealthPolicy)

    @model_validator(mode="after")
    def consistent_scope(self) -> "ServerSettings":
        tokens = set()
        regions: dict[str, str] = {}
        collectors = set()
        source_owners = set()
        for item in self.credentials:
            if item.token_sha256 in tokens:
                raise ValueError("Duplicate credential")
            tokens.add(item.token_sha256)
            if regions.setdefault(item.tenant_id, item.region) != item.region:
                raise ValueError("Tenant must have one configured region")
            if item.collector_id is not None:
                identity = (item.tenant_id, item.collector_id)
                if identity in collectors:
                    raise ValueError("Duplicate collector identity")
                collectors.add(identity)
                for source in item.source_ids:
                    membership = (item.tenant_id, source)
                    if membership in source_owners:
                        raise ValueError("Duplicate source membership")
                    source_owners.add(membership)
        return self


class CollectorSettings(StrictModel):
    tenant_id: Identifier
    collector_id: Identifier
    region: Identifier
    token: SecretStr
    hmac_key: SecretStr
    local_token: SecretStr
    source_keys: Annotated[list[str], Field(min_length=1)]
    saas_url: str = "https://localhost:8443"
    local_port: Annotated[int, Field(ge=1024, le=65535)] = 9001
    outbox_capacity: Annotated[int, Field(ge=1, le=10000)] = 1000

    @field_validator("hmac_key")
    @classmethod
    def valid_key(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) != 64:
            raise ValueError("Expected 32-byte HMAC key")
        try:
            bytes.fromhex(value.get_secret_value())
        except ValueError as error:
            raise ValueError("Expected hex HMAC key") from error
        if len(bytes.fromhex(value.get_secret_value())) != 32:
            raise ValueError("Expected 32-byte HMAC key")
        return value


def read_settings(path: Path, model: type[Model]) -> Model:
    return model.model_validate_json(path.read_bytes())
