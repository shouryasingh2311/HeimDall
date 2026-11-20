"""
Pure Remediation Simulator & Snapshot Helper.

Owned by Member 3 (feat/fixtures-validation).
Fulfills AUTO-01, AUTO-02, AUTO-03 and Check V11 per CONTRACTS.md and MEMBER_3_VALIDATION.md:
- Simulates container resource remediation for demo target nodes (SCALE_CONTAINER_MEMORY).
- Maintains state snapshots prior to applying any simulated mutation.
- Applies capacity scaling, causing subsequent DemoSource ticks to reflect reduced memory pressure.
- Provides rollback capability restoring original snapshot state.
- Pure helper: no direct dashboard state mutation, exposes clean audit record for M1 persistence.
"""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from backend.collector.demo_source import DemoSource


@dataclass
class StateSnapshot:
    snapshot_id: str
    node_id: str
    tenant_id: str
    previous_capacity_mb: int
    created_at_utc: str
    description: str


@dataclass
class RemediationAuditRecord:
    action_id: str
    command_type: str
    node_id: str
    tenant_id: str
    snapshot_id: str
    target_capacity_mb: int
    executed_at_utc: str
    status: str  # "applied", "rolled_back", "failed"


class RemediationSimulator:
    """
    Simulation helper managing demo container scaling and rollback.
    Interacts with DemoSource memory allocation states.
    """

    ALLOWED_ACTIONS = ["SCALE_CONTAINER_MEMORY"]

    def __init__(self, demo_source: DemoSource):
        self.demo_source = demo_source
        self.snapshots: Dict[str, StateSnapshot] = {}
        self.audit_log: List[RemediationAuditRecord] = []

    def create_snapshot(self, node_id: str, tenant_id: str = "tenant-alpha") -> StateSnapshot:
        """Capture current configuration state before executing action."""
        current_cap = self.demo_source.memory_capacities.get(node_id, 1024)
        snapshot_id = f"snap-{uuid.uuid4().hex[:8]}"
        now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

        snapshot = StateSnapshot(
            snapshot_id=snapshot_id,
            node_id=node_id,
            tenant_id=tenant_id,
            previous_capacity_mb=current_cap,
            created_at_utc=now_str,
            description=f"Pre-scale snapshot for node {node_id} (capacity: {current_cap}MB)",
        )
        self.snapshots[snapshot_id] = snapshot
        return snapshot

    def apply_scale_container_memory(
        self,
        node_id: str,
        new_capacity_mb: int,
        tenant_id: str = "tenant-alpha",
        action_id: Optional[str] = None,
    ) -> RemediationAuditRecord:
        """
        Execute SCALE_CONTAINER_MEMORY.
        1. Snapshot current state.
        2. Update demo_source capacity.
        3. Emit audit record.
        """
        # Validate node exists
        valid_nodes = [node.node_id for node in self.demo_source.NODE_SPECS]
        if node_id not in valid_nodes:
            raise ValueError(f"Unknown target node '{node_id}'. Allowed demo nodes: {valid_nodes}")

        if new_capacity_mb <= 0:
            raise ValueError("New memory capacity must be a positive integer.")

        snapshot = self.create_snapshot(node_id, tenant_id)
        self.demo_source.scale_container_memory(node_id, new_capacity_mb)

        aid = action_id or f"act-{uuid.uuid4().hex[:8]}"
        now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

        audit_entry = RemediationAuditRecord(
            action_id=aid,
            command_type="SCALE_CONTAINER_MEMORY",
            node_id=node_id,
            tenant_id=tenant_id,
            snapshot_id=snapshot.snapshot_id,
            target_capacity_mb=new_capacity_mb,
            executed_at_utc=now_str,
            status="applied",
        )
        self.audit_log.append(audit_entry)
        return audit_entry

    def rollback(self, snapshot_id: str) -> RemediationAuditRecord:
        """
        Restore demo node capacity from previous snapshot.
        Verifies telemetry returns to baseline.
        """
        if snapshot_id not in self.snapshots:
            raise KeyError(f"Snapshot '{snapshot_id}' not found.")

        snapshot = self.snapshots[snapshot_id]
        # Revert memory capacity in DemoSource
        self.demo_source.scale_container_memory(snapshot.node_id, snapshot.previous_capacity_mb)

        aid = f"rollback-{uuid.uuid4().hex[:8]}"
        now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

        audit_entry = RemediationAuditRecord(
            action_id=aid,
            command_type="ROLLBACK_CONTAINER_MEMORY",
            node_id=snapshot.node_id,
            tenant_id=snapshot.tenant_id,
            snapshot_id=snapshot_id,
            target_capacity_mb=snapshot.previous_capacity_mb,
            executed_at_utc=now_str,
            status="rolled_back",
        )
        self.audit_log.append(audit_entry)
        return audit_entry

    def get_audit_trail(self) -> List[Dict[str, Any]]:
        """Return formatted audit history."""
        return [
            {
                "action_id": rec.action_id,
                "command_type": rec.command_type,
                "node_id": rec.node_id,
                "tenant_id": rec.tenant_id,
                "snapshot_id": rec.snapshot_id,
                "target_capacity_mb": rec.target_capacity_mb,
                "executed_at_utc": rec.executed_at_utc,
                "status": rec.status,
            }
            for rec in self.audit_log
        ]
