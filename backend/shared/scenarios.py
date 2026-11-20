"""Typed evidence shared by the local simulator and dashboard."""

from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from backend.shared.models import StrictModel, UtcString, UuidString, parse_utc

ScenarioNumber = Annotated[int, Field(ge=1, le=8)]
PayloadIDs = Annotated[list[UuidString], Field(max_length=200)]
RESULT_GRACE_SECONDS = 30


def scenario_timeout(number: int) -> int:
    return 180 if number == 8 else 65


Check = Literal[
    "digest_matches", "secret_excluded", "queued", "reconciled", "four_silent", "five_counted",
    "related", "alert_deadline", "normal_silent", "single_silent", "sustained_alert",
    "unrelated_separate", "duplicate_ack", "late_historical", "approved", "recovered", "restored",
]
PASS_CHECKS = (
    {"digest_matches", "secret_excluded"}, {"queued", "reconciled"}, {"four_silent", "five_counted"},
    {"related", "alert_deadline"}, {"normal_silent", "single_silent", "sustained_alert"},
    {"related", "unrelated_separate"}, {"duplicate_ack", "late_historical"},
    {"approved", "recovered", "restored"},
)


class ScenarioResult(StrictModel):
    run_id: UuidString
    scenario_id: ScenarioNumber
    status: Literal["running", "passed", "failed", "blocked"]
    started_at_utc: UtcString
    finished_at_utc: UtcString | None = None
    checks: dict[Check, bool | int] = Field(default_factory=dict)
    payload_uuids: PayloadIDs = Field(default_factory=list)
    incident_ids: PayloadIDs = Field(default_factory=list)
    missing_ids: PayloadIDs = Field(default_factory=list)
    duplicate_count: Annotated[int, Field(ge=0)] = 0
    reason_code: Literal[
        "evidence_mismatch", "evidence_timeout", "operator_required", "transport_unavailable", "result_not_reported",
    ] | None = None

    @field_validator("started_at_utc", "finished_at_utc")
    @classmethod
    def valid_timestamp(cls, value: str | None):
        if value is not None:
            parse_utc(value)
        return value

    @model_validator(mode="after")
    def consistent_verdict(self):
        if (self.status == "running") != (self.finished_at_utc is None):
            raise ValueError("Only a final result has a finish time")
        if self.finished_at_utc and parse_utc(self.finished_at_utc) < parse_utc(self.started_at_utc):
            raise ValueError("Scenario finished before it started")
        if self.status == "passed" and (
            set(self.checks) != PASS_CHECKS[self.scenario_id - 1] or not all(self.checks.values())
            or not self.payload_uuids or self.missing_ids or self.reason_code
        ):
            raise ValueError("Passing results require observed evidence for each check")
        return self


class ScenarioProbe(StrictModel):
    payload_uuids: PayloadIDs
