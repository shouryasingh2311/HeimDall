"""Rolling anomaly rules and explicit severe thresholds."""

from dataclasses import dataclass, field
from statistics import mean as average, pstdev

from backend.shared.config import HealthPolicy
from backend.shared.models import MetadataPayload, parse_utc

WINDOW = 30
WARMUP = 10
FLOORS = {"cpu_pct": 1., "memory_pct": 1., "latency_ms": 1., "packet_loss_pct": .1}


@dataclass
class Baseline:
    values: list[float] = field(default_factory=list)
    candidate_since: str | None = None
    last_point: str | None = None

    def observe(self, value: float, floor: float, timestamp: str, severe: bool):
        mean = deviation = z = None
        if len(self.values) >= WARMUP:
            mean = average(self.values)
            deviation = max(pstdev(self.values), floor)
            z = (value - mean) / deviation
        candidate = z is not None and z > 3
        previous = self.candidate_since
        if self.last_point and (parse_utc(timestamp) - parse_utc(self.last_point)).total_seconds() >= 30:
            previous = None
        self.last_point = timestamp
        self.candidate_since = (previous or timestamp) if candidate else None
        if not candidate and not severe:
            self.values = [*self.values[-(WINDOW - 1):], value]
        return candidate, previous if candidate else None, mean, deviation, z


@dataclass(frozen=True)
class Signal:
    metric: str
    observed: float
    breach_at: str
    severity: str
    baseline_mean: float | None = None
    baseline_std: float | None = None
    z_score: float | None = None


def evaluate_metrics(payload: MetadataPayload, policy: HealthPolicy, baselines: dict[str, Baseline], timestamp: str):
    metrics = payload.metrics
    if metrics is None:
        raise ValueError("Expected a metric payload")
    severe_limits = {
        "cpu_pct": policy.cpu[-1], "memory_pct": policy.memory[-1], "disk_used_pct": policy.disk[-1],
        "latency_ms": policy.latency[-1], "packet_loss_pct": policy.packet_loss[-1],
        "service_available": None, "connectivity": None,
    }
    signals = []
    normal = set()
    ready = True
    for metric, limit in severe_limits.items():
        value = getattr(metrics, metric)
        if value is None:
            continue
        severe = value is False if limit is None else value >= limit
        candidate = False
        start = mean = deviation = z = None
        if metric in FLOORS:
            baseline = baselines.setdefault(metric, Baseline())
            candidate, start, mean, deviation, z = baseline.observe(value, FLOORS[metric], timestamp, severe)
            ready = ready and mean is not None
        if severe or start:
            # Static alerts measure this breach. A statistical alert measures from
            # the preceding candidate that made this deviation consecutive.
            signals.append(Signal(metric, float(value), timestamp if severe else start,
                                  "critical" if severe else "warning", mean, deviation, z))
        if not severe and not candidate:
            normal.add(metric)
    return signals, normal, ready
