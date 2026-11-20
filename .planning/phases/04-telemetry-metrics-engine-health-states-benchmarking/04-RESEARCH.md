# Phase 4: Telemetry Metrics Engine, Health States & Benchmarking — Research

**Researched:** 2026-11-20
**Domain:** Time-Series Metrics Processing, 4-State Health State Machine, Stale Data Detection, Latency Benchmarking
**Confidence:** HIGH

<user_constraints>
## User Constraints (from Hackathon Guide & PROJECT.md)

### Locked Decisions
- Four Health States: Platform MUST classify collector and system health into `Excellent`, `Good`, `Fair`, and `Poor`.
- Stale Data Degradation: If telemetry stops or heartbeat exceeds threshold (>30s), system MUST downgrade health state rather than holding last good status.
- Real-Time Targets:
  1. Collection-to-Dashboard Latency: $\le 10$ seconds at 95th percentile.
  2. Breach-to-Alert: $\le 15$ seconds.
  3. Offline Detection: $\le 60$ seconds from last heartbeat to status change to `Poor`.
- State Transition Audit: All state changes must carry UTC timestamps and reasons in an immutable event log.

### Claude's Discretion
- Telemetry Ingestion Engine: Python async memory store + SQLite time-series rollups.
- Latency Meter: Embedded timestamp diff calculator comparing `ingest_time_utc - event_timestamp_utc` and `dashboard_render_time - event_timestamp_utc`.
</user_constraints>

<architectural_responsibility_map>
## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
| :--- | :--- | :--- | :--- |
| OS Telemetry Harvester | Tier 1 (Customer Edge) | — | Collects CPU, RAM, disk, latency, loss locally via `psutil` or synthetic generator |
| Heartbeat Daemon | Tier 1 (Customer Edge) | Tier 2 (SaaS Monitor) | Sends pulse every 10s with version, memory footprint, and queue status |
| 4-State Health Evaluator | Tier 2 (Central SaaS) | Dashboard Tier | Evaluates composite metrics against configurable thresholds and stale timers |
| Latency Benchmark Gauge | Tier 2 (Central SaaS) | Dashboard Tier | Measures p50, p90, p95 end-to-end event latencies for judge evaluation |
</architectural_responsibility_map>

<research_summary>
## Summary

Phase 4 delivers the operational heart of the observability platform, implementing the 4 product health states and strict latency benchmarking mandated by Section 4 & Section 2 of the evaluation guide:
1. **Four-State Health State Machine**:
   - `Excellent`: All collectors reporting within 15s; CPU $<70\%$, RAM $<75\%$, Latency $<50\text{ms}$, Loss $0\%$.
   - `Good`: Minor deviations (CPU $70-85\%$, Latency $50-120\text{ms}$), no service disruption.
   - `Fair`: Warning state (CPU $>85\%$, Latency $>120\text{ms}$, Packet loss $>2\%$, or warning count $>5$).
   - `Poor`: Critical failure (Collector heartbeat $>60\text{s}$ overdue, critical security attack, or severe packet loss $>10\%$).
2. **Stale Data Handling**:
   - Monitored nodes have a rolling 30-second TTL. If no fresh telemetry arrives within 30s, health state degrades to `Fair` ("Stale telemetry detected"). At 60s without heartbeat, state switches to `Poor` ("Collector offline").
3. **Latency Benchmarking & SLA Instrumentation**:
   - Injected telemetry timestamps are preserved end-to-end. The platform computes `render_latency = now_utc - event_timestamp_utc` and renders a live 95th-percentile latency gauge on the dashboard to prove compliance with the $\le 10$s target.
</research_summary>

## Key Implementation Patterns
- Discrete state transitions with deterministic reason strings.
- Sliding window latency calculation using NumPy or rolling percentile array.
- Async heartbeat watchdog loop in FastAPI background tasks.
