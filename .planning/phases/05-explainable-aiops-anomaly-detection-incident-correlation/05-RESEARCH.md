# Phase 5: Explainable AIOps Anomaly Detection & Incident Correlation — Research

**Researched:** 2026-11-20
**Domain:** Statistical Baselining (EWMA, Rolling Z-score/MAD), Alert Noise Reduction, Temporal-Topological Correlation, Explainable AI Decision Chains
**Confidence:** HIGH

<user_constraints>
## User Constraints (from Hackathon Guide & PROJECT.md)

### Locked Decisions
- Beyond Static Thresholds: AIOps MUST dynamically differentiate true anomalies from normal usage spikes (e.g. diurnal patterns, scheduled cron jobs).
- Alert Noise Reduction: Cascading alerts across CPU, network, and application components must be clustered into a single correlated Incident object.
- Edge Security Scoring: Repeated failed logins must be detected locally on the collector to compute a risk score without shipping raw credential attempts.
- Explainability (Weighted Higher by Judges): Every recommendation must explicitly present:
  1. Contributing signals (e.g., `CPU: +3.4σ above baseline`, `Packet Loss: 8%`, `Auth Failure: 25 attempts/min`).
  2. Baseline comparison (observed value vs. expected baseline window).
  3. Confidence score (percentage based on signal consensus).
  4. Human-readable reasoning path tracing cause to proposed action.

### Claude's Discretion
- Anomaly Model: Exponentially Weighted Moving Average (EWMA) + Rolling Median Absolute Deviation (MAD) / Robust Z-score.
- Correlation Engine: Sliding time-window (60s) graph clustering connecting alerts sharing node topology or downstream service dependencies.
</user_constraints>

<architectural_responsibility_map>
## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
| :--- | :--- | :--- | :--- |
| Local Security Threat Detector | Tier 1 (Customer Edge) | — | Analyzes auth logs locally, emits `risk_score` and `event_category: auth_brute_force` |
| Dynamic Baseline Engine | Tier 2 (Central SaaS) | — | Calculates rolling mean/std-dev per metric time series; detects statistical outliers |
| Multi-Signal Correlation Engine | Tier 2 (Central SaaS) | — | Groups related alert events into unified incidents within a temporal-spatial sliding window |
| Explainable Reasoning Generator | Tier 2 (Central SaaS) | Dashboard Tier | Synthesizes contributing signals, confidence metrics, and causal explanation trees |
</architectural_responsibility_map>

<research_summary>
## Summary

Phase 5 delivers the core intelligence of the platform and directly targets the highest-weighted scoring criteria in Checkpoint 2 and Checkpoint 4:
1. **Dynamic Statistical Baselining (EWMA + Rolling Z-Score)**:
   - Maintains an online Exponentially Weighted Moving Average (EWMA) and rolling variance for each metric (`cpu_usage`, `memory_usage`, `network_latency`, `packet_loss`).
   - Computes dynamic bounds: $[\mu - k\sigma, \mu + k\sigma]$. Spikes within normal variance or predictable diurnal shifts are filtered out; statistically anomalous excursions ($|Z| > 3.0$) trigger anomaly events with exact standard deviation deltas.
2. **Local Security Risk Scoring (Tier 1)**:
   - Collector monitors auth events locally. If $> 5$ failed login attempts occur within 10 seconds, it increments local threat state and emits a sanitized alert: `{event_type: "auth_anomaly", severity: "high", risk_score: 85, context: "5 failed logins in 10s from pseudonymous IP"}` without transmitting usernames or passwords.
3. **Temporal-Topological Incident Correlation**:
   - Instead of firing 10 separate notifications when a database CPU spike causes API latency and web errors, the correlation engine aggregates events occurring within a 60-second window across related nodes into a single Incident.
4. **Explainable AI Recommendation Engine**:
   - Produces structured explanations:
     - `incident_id`: `INC-2026-081`
     - `root_cause`: "Database node exhaustion cascading to API latency"
     - `contributing_signals`: `[{"metric": "cpu", "observed": 96.2, "baseline": 42.1, "z_score": 3.8, "weight": 0.45}, ...]`
     - `confidence`: 92%
     - `reasoning_path`: "Observed CPU spiked 3.8σ at 14:02:10 -> 12 seconds later API gateway latency degraded from 24ms to 480ms -> 3 HTTP 504 timeouts logged."
     - `suggested_action`: "Scale DB memory pool or terminate runaway PID 4108"
</research_summary>

## Key Implementation Patterns
- Online EWMA algorithm without heavy database re-scans.
- Sliding window event aggregation buffer.
- Deterministic explainability templates backed by quantitative signal vectors.
