# Phase 7: Interactive Chaos Engine & 8 Live Validation Scenarios — Research

**Researched:** 2026-11-20
**Domain:** Synthetic Telemetry Streaming, Chaos Engineering, Failure Injection, Deterministic Test Harnesses
**Confidence:** HIGH

<user_constraints>
## User Constraints (from Hackathon Guide & PROJECT.md)

### Locked Decisions
- 8 Mandatory Scenarios: The platform MUST provide single-click / API execution for all 8 scenarios specified in Section 8 of the Hackathon Guide.
- Organizer-Provided Stream Simulation: Continuous synthetic telemetry stream simulating multi-node enterprise environments (e.g., `web-01`, `api-gw`, `auth-service`, `db-primary`).
- Timestamp Authenticity: Injected events must preserve microsecond UTC timestamps for accurate latency measurement.
- Live Demonstration Ready: Judges can trigger any scenario on the spot without rehearsals or brittle test scripts.

### Claude's Discretion
- Implementation: Python async chaos generator with REST API endpoints (`/api/v1/chaos/scenario/{1..8}`).
- State Machine: Supports toggling chaos states on and off to observe system return to `Excellent` health.
</user_constraints>

<architectural_responsibility_map>
## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
| :--- | :--- | :--- | :--- |
| Synthetic Stream Producer | Tier 1 (Customer Edge) | — | Emits background baseline telemetry to collector harvester |
| Chaos Injector Engine | Tier 1 & Tier 2 | Dashboard Tier | Injects specific anomalies (secrets, outages, brute-force, spikes) |
| Scenario Verification Harness | Tier 2 (Central SaaS) | CLI / UI | Automatically checks expected outcomes and marks scenarios PASS/FAIL |
</architectural_responsibility_map>

<research_summary>
## Summary

Phase 7 builds the evaluation harness that proves compliance with Section 8 of the Hackathon Guide. The engine supports all 8 required validation scenarios:
- **Scenario 1 (Secret in Log)**: Injects `{"log": "Failed to connect to db with pass=Admin@123 and token=ghp_9843b..."}` into collector input; verifies local scrubber redacts it and SaaS receives only sanitized metadata.
- **Scenario 2 (Collector Outage)**: Severely cuts SaaS endpoint connectivity; verifies collector transitions to offline buffer, stores records in SQLite, reconnects, and replays 100% of backlog with zero loss.
- **Scenario 3 (Failed Logins)**: Injects 15 rapid failed login events; verifies collector security analyzer emits risk score 90 without transmitting usernames/passwords.
- **Scenario 4 (Network Latency Rise)**: Injects latency jump from 25ms to 350ms with 5% packet loss; verifies threshold breach alert within 15 seconds.
- **Scenario 5 (Baseline Deviation)**: Injects CPU drift from 35% to 92%; verifies AIOps dynamic baselining flags statistical anomaly ($Z > 3.0$).
- **Scenario 6 (Alert Storm Correlation)**: Fires simultaneous alerts on DB CPU, API latency, and 504 errors; verifies incident correlator consolidates them into 1 root incident.
- **Scenario 7 (Duplicate / Out-of-Order)**: Injects out-of-order packets and duplicate payload UUIDs; verifies SaaS idempotency drops duplicates and orders time series by event timestamp.
- **Scenario 8 (Remediation Proposal)**: Triggers an operational incident proposing a service restart; verifies policy check, interactive approval modal, audit logging, and rollback restoration.
</research_summary>

## Key Implementation Patterns
- Discrete endpoint triggers `/api/v1/chaos/trigger/{scenario_id}`.
- Automated validation assertions returning structured `{scenario, expected, observed, pass: bool}`.
