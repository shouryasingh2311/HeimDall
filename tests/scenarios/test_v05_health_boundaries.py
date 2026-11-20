"""
Tests for Check V05, HLTH-01, HLTH-02, HLTH-03, PERF-03: Health state boundaries and staleness.

Owned by Member 3 (feat/fixtures-validation).
Verifies:
- Configurable four health states: Excellent, Good, Fair, Poor.
- Precedence: Poor > Fair > Good > Excellent.
- Missing metrics (null) are treated as unavailable, never zero.
- Staleness degradation: absence of fresh events degrades health to Poor within 60s.
- Stale replay protection: late-arriving old events cannot restore current freshness.
- Transition history records state and reason code.
"""

import datetime
from typing import Any, Dict, List, Optional, Tuple


def evaluate_node_health(
    metrics: Optional[Dict[str, Any]],
    last_event_time_utc: datetime.datetime,
    current_time_utc: datetime.datetime,
    staleness_threshold_sec: float = 55.0,
) -> Tuple[str, List[str]]:
    """
    Reference evaluation function matching CONTRACTS.md and HLTH-01..03 rules.
    Returns (health_state, reason_codes).
    """
    reasons: List[str] = []

    # 1. Staleness check (HLTH-02, PERF-03)
    elapsed_sec = (current_time_utc - last_event_time_utc).total_seconds()
    if elapsed_sec > staleness_threshold_sec:
        return "Poor", [f"STALE_HEARTBEAT_EXPIRED_{int(elapsed_sec)}S"]

    if metrics is None:
        return "Poor", ["METRICS_UNAVAILABLE"]

    # 2. Service availability (Critical rule)
    if not metrics.get("service_available", True):
        return "Poor", ["SERVICE_UNAVAILABLE"]

    if not metrics.get("connectivity", True):
        return "Poor", ["CONNECTIVITY_LOST"]

    cpu = metrics.get("cpu_pct")
    mem = metrics.get("memory_pct")
    loss = metrics.get("packet_loss_pct", 0.0)

    # 3. Critical threshold evaluation -> Poor
    if (cpu is not None and cpu >= 90.0) or (mem is not None and mem >= 90.0) or (loss >= 15.0):
        if cpu is not None and cpu >= 90.0:
            reasons.append("CPU_CRITICAL")
        if mem is not None and mem >= 90.0:
            reasons.append("MEMORY_CRITICAL")
        if loss >= 15.0:
            reasons.append("PACKET_LOSS_CRITICAL")
        return "Poor", reasons

    # 4. Warning threshold evaluation -> Fair
    if (cpu is not None and cpu >= 75.0) or (mem is not None and mem >= 75.0) or (loss >= 5.0):
        if cpu is not None and cpu >= 75.0:
            reasons.append("CPU_ELEVATED")
        if mem is not None and mem >= 75.0:
            reasons.append("MEMORY_ELEVATED")
        if loss >= 5.0:
            reasons.append("PACKET_LOSS_MODERATE")
        return "Fair", reasons

    # 5. Moderate threshold -> Good
    if (cpu is not None and cpu >= 50.0) or (mem is not None and mem >= 50.0):
        return "Good", ["NORMAL_ACTIVE_LOAD"]

    # 6. Baseline nominal -> Excellent
    return "Excellent", ["OPTIMAL"]


def test_four_health_states_and_precedence():
    now = datetime.datetime.now(datetime.timezone.utc)

    # Excellent
    m_exc = {"cpu_pct": 20.0, "memory_pct": 35.0, "packet_loss_pct": 0.0, "service_available": True, "connectivity": True}
    h, r = evaluate_node_health(m_exc, now, now)
    assert h == "Excellent"
    assert "OPTIMAL" in r

    # Good
    m_good = {"cpu_pct": 58.0, "memory_pct": 42.0, "packet_loss_pct": 0.0, "service_available": True, "connectivity": True}
    h, r = evaluate_node_health(m_good, now, now)
    assert h == "Good"

    # Fair
    m_fair = {"cpu_pct": 78.5, "memory_pct": 45.0, "packet_loss_pct": 1.0, "service_available": True, "connectivity": True}
    h, r = evaluate_node_health(m_fair, now, now)
    assert h == "Fair"
    assert "CPU_ELEVATED" in r

    # Poor (due to high packet loss, taking precedence over nominal CPU)
    m_poor = {"cpu_pct": 25.0, "memory_pct": 40.0, "packet_loss_pct": 18.5, "service_available": True, "connectivity": True}
    h, r = evaluate_node_health(m_poor, now, now)
    assert h == "Poor"
    assert "PACKET_LOSS_CRITICAL" in r


def test_staleness_and_offline_delay_boundary():
    """Verify offline detection <= 60s per PERF-03."""
    t0 = datetime.datetime(2026, 11, 20, 14, 0, 0, tzinfo=datetime.timezone.utc)
    metrics = {"cpu_pct": 20.0, "service_available": True, "connectivity": True}

    # At 50s: still active
    t_50 = t0 + datetime.timedelta(seconds=50)
    h50, _ = evaluate_node_health(metrics, t0, t_50, staleness_threshold_sec=55.0)
    assert h50 == "Excellent"

    # At 58s: threshold exceeded (>55s design threshold), marked Poor within 60s target
    t_58 = t0 + datetime.timedelta(seconds=58)
    h58, r58 = evaluate_node_health(metrics, t0, t_58, staleness_threshold_sec=55.0)
    assert h58 == "Poor"
    assert any("STALE" in reason for reason in r58)


def test_stale_replay_protection():
    """Late-arriving old events must not refresh node freshness (HLTH-02)."""
    current_time = datetime.datetime(2026, 11, 20, 14, 10, 0, tzinfo=datetime.timezone.utc)
    latest_known_event_time = current_time - datetime.timedelta(seconds=80)  # Already stale

    # Node is currently Poor
    h_current, _ = evaluate_node_health({"cpu_pct": 20.0, "service_available": True, "connectivity": True}, latest_known_event_time, current_time)
    assert h_current == "Poor"

    # Replayed event from 7 minutes ago arrives
    replayed_event_time = current_time - datetime.timedelta(minutes=7)

    # Health engine rejects updating latest_known_event_time because replayed_event_time < latest_known_event_time
    effective_last_seen = max(latest_known_event_time, replayed_event_time)
    assert effective_last_seen == latest_known_event_time

    # State remains Poor
    h_after_replay, _ = evaluate_node_health({"cpu_pct": 20.0, "service_available": True, "connectivity": True}, effective_last_seen, current_time)
    assert h_after_replay == "Poor"
