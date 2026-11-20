# Cicada AIOps Observability Platform

## What This Is

Cicada is an end-to-end, privacy-first AIOps observability platform designed to monitor distributed enterprise, data center, cloud, and edge infrastructures without exposing sensitive operational data outside customer environments. Using a two-tier architecture, a lightweight local collector gathers telemetry, performs local filtering, secret scrubbing, and local threat analysis, and transmits strictly allow-listed metadata to a centralized multi-tenant SaaS platform that delivers explainable AIOps anomaly detection, alert correlation, and policy-governed autonomous remediation workflows.

## Core Value

Zero raw telemetry or credentials leave the customer environment, verified by a local Egress Proof Panel, while the SaaS platform delivers real-time, explainable AIOps correlation and actionable operational recommendations.

## Business Context

- **Customer**: Enterprise infrastructure teams, data center operators, and cloud SecOps needing unified visibility across sovereign and regulated environments.
- **Revenue model**: Tiered SaaS per active monitored node / collector with enterprise compliance and autonomous ops add-ons.
- **Success metric**: 100% compliance on zero raw data leakage, $\le 10$s collection-to-dashboard latency at p95, and $\ge 80\%$ alert noise reduction through multi-signal correlation.
- **Strategy notes**: Built for the CICADA 2026 24-Hour Smart Observability Hackathon, optimized to score maximum marks across all 4 evaluation phases and 8 live validation scenarios.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] **ARCH-01**: Two-tier architecture with clear trust boundary separating Tier 1 (Customer Collector) and Tier 2 (Central SaaS) over authenticated, encrypted TLS endpoints.
- [ ] **PRIV-01**: Local data protection pipeline enforcing strict field allow-listing, regex secret scrubbing (passwords, API tokens, bearer keys), and pseudonymous source identifiers before any transmission.
- [ ] **PRIV-02**: Local Egress Proof Panel providing a tamper-evident visual and auditable log of the exact payload contents before leaving the customer environment.
- [ ] **BUFF-01**: Durable local outage buffering (SQLite WAL) queueing approved metadata during SaaS unavailability and resuming delivery upon reconnect with zero record loss.
- [ ] **IDEM-01**: Idempotent delivery and out-of-order event placement using deterministic UUIDs and UTC timestamps to guarantee zero duplicate records and intact trends.
- [ ] **PERF-01**: Real-time performance meeting hackathon targets: $\le 10$s collection-to-dashboard latency (p95), $\le 15$s threshold breach to alert, and $\le 60$s collector offline detection.
- [ ] **HLTH-01**: Four-state health evaluation (`Excellent`, `Good`, `Fair`, `Poor`) across collectors and monitored systems with automatic state downgrades on stale or missing data.
- [ ] **AIOP-01**: AIOps anomaly detection using dynamic baselines (EWMA, rolling Z-score/MAD) detecting deviations beyond static threshold spikes.
- [ ] **AIOP-02**: Multi-signal alert correlation grouping related infrastructure, network, and security alerts into unified incidents to eliminate alert fatigue.
- [ ] **AIOP-03**: Explainable AIOps recommendations showing exact contributing signals, deviation baselines, confidence scores, and reasoning paths.
- [ ] **AUTO-01**: Policy-governed Autonomous Ops simulator with interactive human-in-the-loop approval, audit trail logging, and rollback safeguards.
- [ ] **SIMU-01**: Interactive Chaos & Telemetry Simulation Engine capable of generating normal multi-node telemetry and 1-click injection of all 8 hackathon evaluation scenarios.
- [ ] **DASH-01**: Production-ready unified dashboard featuring side-by-side comparison (Local Collector Egress vs. Central SaaS Ingestion), multi-tenant fleet views, and scenario controls.

### Out of Scope

- Centralized raw log lake — Storing raw logs centrally violates sovereign data compliance and hackathon local-first data protection mandate.
- Unbounded autonomous infrastructure remediation — Direct, unapproved destructive remediation commands on live infrastructure are prohibited; only simulated, human-approved, rollback-safe actions are in scope.
- Proprietary cloud-only dependencies — The system must be deployable anywhere (on-prem, VM, edge, cloud container) without requiring proprietary cloud vendor services.

## Context

- Hackathon: CICADA 2026 | 24-Hour Hackathon (TechForcz x Atria Institute of Technology).
- Evaluation: 4 Judging Phases (Problem Understanding & Ideation [10m], Architecture & Technical Design [25m], Implementation & Working Prototype [35m], Final Demo & Presentation [30m]).
- Mandatory Benchmarks: Real-time targets measured from simulated stream timestamps; Egress Proof Panel; side-by-side raw vs. redacted proof; 8 live scenario responses.

## Constraints

- **Timeline**: 24-hour hackathon execution window.
- **Security**: Zero raw logs, secrets, or unapproved fields may cross the network boundary.
- **Portability**: Must be deployable anywhere as lightweight, self-contained runtimes (Python/Node/Docker).
- **Compliance**: Tenant isolation enforced at API ingestion and storage layer; strict multi-tenancy.

## Key Decisions

| Decision | Rationale | Outcome |
| :--- | :--- | :--- |
| **Two-Tier Architecture** | Decouples local edge ingestion from central analytics, enforcing physical separation of raw vs. metadata. | — Pending |
| **Local-First Scrubbing & Egress Panel** | Guarantees compliance before network socket creation and provides visual proof for judges and compliance officers. | — Pending |
| **SQLite WAL Offline Buffer** | Provides crash-resilient, zero-loss local spooling during SaaS outages with zero external database dependencies. | — Pending |
| **Statistical AIOps (EWMA + Z-score)** | Fast, lightweight, explainable anomaly detection running in milliseconds without GPU or heavy cloud model dependencies. | — Pending |
| **Python FastAPI + Next.js/React Dashboard** | Optimal pairing of high-performance analytics/API backend with polished, responsive UI for hackathon demonstrations. | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-11-20 after initialization*