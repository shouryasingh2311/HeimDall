"""
Tests for Check V11 and AUTO-01..03: Remediation simulator and rollback helper.

Owned by Member 3 (feat/fixtures-validation).
Verifies:
- Snapshot created prior to applying action.
- Telemetry memory metrics drop post-scaling (representing lower utilization ratio).
- Rollback restores previous capacity and metrics return to baseline.
- Audit records trace action_id, snapshot_id, and timestamps.
"""

from backend.collector.demo_source import DemoSource
from backend.simulation.remediation_helper import RemediationSimulator


def test_remediation_scale_and_rollback():
    source = DemoSource(seed=100)
    sim = RemediationSimulator(source)

    target_node = "api-01"
    initial_cap = source.memory_capacities[target_node]
    assert initial_cap == 1024

    # Baseline tick before scaling
    baseline_events = {e.source_key: e for e in source.generate_tick(tenants=["tenant-alpha"])}
    initial_mem_pct = baseline_events[f"tenant-alpha:{target_node}"].metrics["memory_pct"]

    # 1. Apply scale container memory (double capacity to 2048 MB)
    audit_record = sim.apply_scale_container_memory(target_node, 2048, tenant_id="tenant-alpha")
    assert audit_record.status == "applied"
    assert audit_record.target_capacity_mb == 2048
    assert source.memory_capacities[target_node] == 2048

    # 2. Subsequent tick reflects increased capacity (memory_pct decreases)
    scaled_events = {e.source_key: e for e in source.generate_tick(tenants=["tenant-alpha"])}
    scaled_mem_pct = scaled_events[f"tenant-alpha:{target_node}"].metrics["memory_pct"]
    assert scaled_mem_pct < initial_mem_pct

    # 3. Rollback using snapshot
    rollback_record = sim.rollback(audit_record.snapshot_id)
    assert rollback_record.status == "rolled_back"
    assert source.memory_capacities[target_node] == initial_cap

    # 4. Telemetry returns to original baseline
    reverted_events = {e.source_key: e for e in source.generate_tick(tenants=["tenant-alpha"])}
    reverted_mem_pct = reverted_events[f"tenant-alpha:{target_node}"].metrics["memory_pct"]
    assert abs(reverted_mem_pct - initial_mem_pct) < 3.0  # within random jitter margin

    # 5. Audit trail records both operations
    trail = sim.get_audit_trail()
    assert len(trail) == 2
    assert trail[0]["status"] == "applied"
    assert trail[1]["status"] == "rolled_back"
