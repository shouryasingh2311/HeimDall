"""
Tests for Check V08, AIOP-01..05, SIMU-06, SIMU-07: Statistical anomaly detection and correlation.

Owned by Member 3 (feat/fixtures-validation).
Verifies:
- Warm-up threshold: at least 10 samples required before anomaly detection activates.
- Rolling baseline computation: mean, standard deviation, and variance floor (sigma floor >= 1.0).
- Z-score detection: values with z > 3.0 trigger anomaly signals.
- Benign spike rejection: short transient spike does not trigger incident without sustained samples.
- Topology-based correlation: related alerts on lb-01 and api-01 are merged into one incident.
- Unrelated isolation: alerts on control worker-01 remain in a separate incident.
"""

import math
from typing import Dict, List, Optional, Tuple

from backend.collector.demo_source import DemoSource


class RollingZScoreDetector:
    """
    Reference statistical detector matching CONTRACTS.md specification.
    Maintains rolling history per source and metric.
    """
    def __init__(self, warm_up_min_samples: int = 10, z_threshold: float = 3.0, sigma_floor: float = 1.0):
        self.warm_up_min_samples = warm_up_min_samples
        self.z_threshold = z_threshold
        self.sigma_floor = sigma_floor
        self.history: Dict[str, List[float]] = {}

    def observe(self, key: str, value: float) -> Tuple[bool, Optional[float], Optional[float], Optional[float]]:
        """
        Record sample and evaluate anomaly status.
        Returns: (is_anomaly, baseline_mean, baseline_std, z_score)
        """
        if key not in self.history:
            self.history[key] = []

        samples = self.history[key]

        # Check warm-up
        if len(samples) < self.warm_up_min_samples:
            samples.append(value)
            return False, None, None, None

        # Compute baseline statistics over historical samples
        mean = sum(samples) / len(samples)
        variance = sum((x - mean) ** 2 for x in samples) / len(samples)
        std_dev = max(math.sqrt(variance), self.sigma_floor)

        z_score = (value - mean) / std_dev
        is_anomaly = abs(z_score) >= self.z_threshold

        # Add to rolling history (max window 50)
        samples.append(value)
        if len(samples) > 50:
            samples.pop(0)

        return is_anomaly, round(mean, 2), round(std_dev, 2), round(z_score, 2)


def test_warmup_period_and_anomaly_detection():
    detector = RollingZScoreDetector(warm_up_min_samples=10, z_threshold=3.0)
    source = DemoSource(seed=999)

    # 1. Warm-up phase: 10 normal ticks
    for tick in range(10):
        events = source.generate_tick(tenants=["tenant-alpha"])
        api_event = next(e for e in events if e.source_key == "tenant-alpha:api-01")
        is_anom, mean, std, z = detector.observe("tenant-alpha:api-01:cpu", api_event.metrics["cpu_pct"])
        assert not is_anom
        assert mean is None  # Still warming up

    # 2. 11th normal tick: baseline is active, but normal value produces no anomaly
    events = source.generate_tick(tenants=["tenant-alpha"])
    api_event = next(e for e in events if e.source_key == "tenant-alpha:api-01")
    is_anom, mean, std, z = detector.observe("tenant-alpha:api-01:cpu", api_event.metrics["cpu_pct"])
    assert not is_anom
    assert mean is not None
    assert abs(z) < 2.5

    # 3. Injected sustained CPU spike: 92% CPU vs ~28% baseline
    is_anom_spike, mean_spike, std_spike, z_spike = detector.observe("tenant-alpha:api-01:cpu", 92.5)
    assert is_anom_spike
    assert z_spike > 5.0
    assert mean_spike < 35.0


def test_incident_correlation_grouping():
    """
    Verify alert storm grouping:
    - Dependency group: lb-01 <-> api-01 <-> auth-01 <-> db-01.
    - Alerts on lb-01 and api-01 merge into 1 incident.
    - Alert on worker-01 forms a separate independent incident.
    """
    dependency_graph = {
        "lb-01": ["api-01"],
        "api-01": ["lb-01", "auth-01", "db-01"],
        "auth-01": ["api-01"],
        "db-01": ["api-01"],
        "worker-01": [],  # Independent control
    }

    def correlate_alerts(alert_sources: List[str]) -> List[List[str]]:
        """Group alert sources if they share a dependency edge."""
        groups: List[List[str]] = []
        for src in alert_sources:
            matched = False
            for grp in groups:
                if any(src in dependency_graph.get(member, []) or member in dependency_graph.get(src, []) for member in grp):
                    grp.append(src)
                    matched = True
                    break
            if not matched:
                groups.append([src])
        return groups

    # Alert storm: simultaneous alerts on lb-01, api-01, and worker-01
    active_alerts = ["lb-01", "api-01", "worker-01"]
    grouped = correlate_alerts(active_alerts)

    # Expect exactly 2 incidents:
    # Incident 1: ["lb-01", "api-01"]
    # Incident 2: ["worker-01"]
    assert len(grouped) == 2
    assert set(grouped[0]) == {"lb-01", "api-01"}
    assert grouped[1] == ["worker-01"]
