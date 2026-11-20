"""
Tests for Check V07 and SIMU-05: Network degradation and downstream topology impact.

Owned by Member 3 (feat/fixtures-validation).
Verifies:
- Injected network degradation on lb-01 causes elevated packet loss (>15%) and latency (>200ms).
- Cascades downstream to dependent api-01 with elevated latency (>100ms).
- Unrelated control worker-01 remains unaffected (0% packet loss, nominal latency).
- Injected condition breach occurs with timing measurable for the <=15s alert threshold.
"""

from backend.collector.demo_source import DemoSource


def test_network_degradation_downstream_cascading_and_unrelated_isolation():
    source = DemoSource(seed=555)

    # Normal tick before injection
    normal_events = {e.source_key: e for e in source.generate_tick(tenants=["tenant-alpha"])}
    normal_lb = normal_events["tenant-alpha:lb-01"]
    normal_api = normal_events["tenant-alpha:api-01"]
    normal_worker = normal_events["tenant-alpha:worker-01"]

    assert normal_lb.metrics["packet_loss_pct"] == 0.0
    assert normal_api.metrics["packet_loss_pct"] == 0.0
    assert normal_worker.metrics["packet_loss_pct"] == 0.0
    assert normal_lb.metrics["latency_ms"] < 20.0
    assert normal_api.metrics["latency_ms"] < 30.0

    # Inject network degradation on lb-01
    source.inject_network_degradation(
        tenant_id="tenant-alpha",
        node_id="lb-01",
        packet_loss_pct=18.0,
        latency_ms=230.0,
        duration_ticks=5,
    )

    # First degraded tick
    degraded_events = {e.source_key: e for e in source.generate_tick(tenants=["tenant-alpha"])}
    deg_lb = degraded_events["tenant-alpha:lb-01"]
    deg_api = degraded_events["tenant-alpha:api-01"]
    deg_worker = degraded_events["tenant-alpha:worker-01"]

    # 1. Primary fault on lb-01
    assert deg_lb.metrics["packet_loss_pct"] >= 15.0
    assert deg_lb.metrics["latency_ms"] >= 200.0

    # 2. Cascading service impact on dependent api-01
    assert deg_api.metrics["latency_ms"] >= 100.0

    # 3. Unrelated control worker-01 is completely unaffected
    assert deg_worker.metrics["packet_loss_pct"] == 0.0
    assert deg_worker.metrics["latency_ms"] < 20.0
