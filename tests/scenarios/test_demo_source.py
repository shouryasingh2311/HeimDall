"""
Tests for DemoSource deterministic generator.

Owned by Member 3 (feat/fixtures-validation).
Verifies:
- 5 nodes generated per tenant (4 dependent + 1 control).
- Bounded metric ranges [0..100] for percentages.
- Seeded reproducibility.
- Network degradation cascading impact from lb-01 to api-01.
"""

import pytest
from backend.collector.demo_source import DemoSource


def test_demo_source_tick_structure_and_bounds():
    source = DemoSource(seed=123, run_id="test-run")
    events = source.generate_tick()

    # 2 tenants * 5 nodes = 10 events per tick
    assert len(events) == 10

    tenants = {ev.tenant_id for ev in events}
    assert tenants == {"tenant-alpha", "tenant-beta"}

    for ev in events:
        assert ev.kind == "metric"
        assert ev.metrics is not None
        m = ev.metrics
        assert 0.0 <= m["cpu_pct"] <= 100.0
        assert 0.0 <= m["memory_pct"] <= 100.0
        assert 0.0 <= m["disk_used_pct"] <= 100.0
        assert m["latency_ms"] >= 0.0
        assert 0.0 <= m["packet_loss_pct"] <= 100.0
        assert isinstance(m["service_available"], bool)
        assert isinstance(m["connectivity"], bool)


def test_demo_source_seeded_reproducibility():
    s1 = DemoSource(seed=42, run_id="fixed-run")
    s2 = DemoSource(seed=42, run_id="fixed-run")

    tick1 = s1.generate_tick()
    tick2 = s2.generate_tick()

    for e1, e2 in zip(tick1, tick2):
        assert e1.input_id == e2.input_id
        assert e1.source_key == e2.source_key
        assert e1.metrics == e2.metrics


def test_network_degradation_cascading_impact():
    source = DemoSource(seed=42)
    # Inject degradation on lb-01 for tenant-alpha
    source.inject_network_degradation("tenant-alpha", "lb-01", packet_loss_pct=20.0, latency_ms=250.0)

    events = source.generate_tick()
    event_map = {ev.source_key: ev for ev in events}

    lb_ev = event_map["tenant-alpha:lb-01"]
    api_ev = event_map["tenant-alpha:api-01"]
    worker_ev = event_map["tenant-alpha:worker-01"]

    # lb-01 has injected degradation
    assert lb_ev.metrics["packet_loss_pct"] >= 15.0
    assert lb_ev.metrics["latency_ms"] >= 200.0

    # api-01 has cascading latency impact
    assert api_ev.metrics["latency_ms"] > 100.0

    # worker-01 (unrelated control) remains unaffected
    assert worker_ev.metrics["packet_loss_pct"] == 0.0
    assert worker_ev.metrics["latency_ms"] < 20.0
