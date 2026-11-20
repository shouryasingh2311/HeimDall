"""Closed wire contracts for the demo-only memory playbook."""

from typing import Annotated, Literal

from pydantic import Field, model_validator

from backend.shared.models import Identifier, Pseudonym, StrictModel, UuidString

PLAYBOOK = "SCALE_CONTAINER_MEMORY"
FACTOR = 1.5
MAX_CAPACITY = 1_048_576
Capacity = Annotated[int, Field(ge=1, le=MAX_CAPACITY)]


def scaled_capacity(before: int) -> int:
    return before * 3 // 2


class DemoCommand(StrictModel):
    command_id: UuidString
    action_id: UuidString
    tenant_id: Identifier
    collector_id: Identifier
    target_source_id: Pseudonym
    kind: Literal["scale", "rollback"]
    playbook: Literal["SCALE_CONTAINER_MEMORY"]
    factor: Literal[1.5]
    simulation: Literal[True]


class CommandResult(StrictModel):
    simulation: Literal[True]
    outcome: Literal["succeeded", "failed"]
    reason_code: Literal["applied", "snapshot_restored", "capacity_limit", "snapshot_missing", "capacity_changed"]
    before_capacity_mb: Capacity | None = None
    after_capacity_mb: Capacity | None = None

    @model_validator(mode="after")
    def matching_outcome(self):
        success = self.reason_code in {"applied", "snapshot_restored"}
        capacities = self.before_capacity_mb is not None and self.after_capacity_mb is not None
        if success != (self.outcome == "succeeded") or success != capacities:
            raise ValueError("Result reason and capacity must match the outcome")
        if not success and (self.before_capacity_mb is not None or self.after_capacity_mb is not None):
            raise ValueError("Failed result must omit capacities")
        return self
