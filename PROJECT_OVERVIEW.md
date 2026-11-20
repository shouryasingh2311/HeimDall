# Heimdal — project idea and team starting guide

## What are we building?

A privacy-first observability web application for infrastructure teams. It monitors system/network/security health without uploading raw logs, passwords or detailed sensitive records to a central service.

It has two parts:
1. A local Python collector running inside the customer environment. It reads organizer telemetry, analyzes failed logins locally, constructs approved metadata, retains raw data locally, and buffers outbound metadata during outages.
2. A central SaaS-style API and React dashboard. It receives authenticated metadata, separates tenants, shows health/trends, detects statistical anomalies, groups related alerts and explains likely causes and suggested actions.

This is an eight-hour hackathon prototype, not a production SaaS product. The supplied PDF describes a 24-hour event; our execution budget is eight hours.

## What judges should see

- Raw synthetic secrets visible only on a separate local proof page; actual approved outbound bytes match the SaaS receipt.
- Four health states: Excellent, Good, Fair and Poor, with reasons and stale/offline handling.
- Durable outage recovery with matching event ID sets and no duplicate analytic effects.
- Anomaly explanation with observed value, baseline, contributing payload IDs, likely cause and transparent heuristic evidence score.
- Related alerts merged while unrelated simultaneous incidents remain separate.
- One operator-approved simulated memory-capacity change, fresh recovery telemetry, audit trail and snapshot rollback.
- All eight scenario behaviors, plus actual render/alert/offline timing and two-tenant isolation.

## Technology stack

| Area | Choice |
|---|---|
| Collector/API | Python 3.11+, FastAPI, Uvicorn |
| Validation/contracts | Pydantic v2, explicit nested schemas |
| HTTPS client | HTTPX with CA and hostname verification |
| Persistence | SQLite WAL/FULL through aiosqlite; one writer/process |
| UI | React, TypeScript, Vite, plain CSS/simple SVG |
| Live updates | Two-second HTTP polling |
| Detection | One rolling mean/std z-score detector; local auth counter |
| Correlation | Tenant + configured dependency group + time window |
| Tests | pytest core/scenarios; focused browser validation |
| Collaboration | Git feature branches, small PRs, lead integration |

Freeze working dependencies and commit lockfiles during setup. No external LLM service is part of the app; coding assistants help build it. No Redis/Kafka/Kubernetes or real cloud deployment is needed for the prototype.

## Team split

M1 uses GPT-6.2 Sol with high reasoning and owns architecture, contracts, collector and API security, buffering, deduplication, health, AIOps, remediation policy and integration.
M2 (teammate, Gemini Flash setup): frontend scaffold/client, fleet/trend/receipt/incident screens, approval UI and genuine render timing.
M3 (teammate, Gemini Flash setup): organizer adapter, seeded demo input, pure snapshot simulator, local proof-page layout, eight scenario inputs/verifier and runbook.

All three contribute across the eight phases; read the [phase ownership matrix](.planning/TEAM_EXECUTION.md). The model labels are user-selected tools, not an assertion about their public availability.

## Architecture rules everyone must follow

Raw input never crosses to SaaS, even to make a nicer comparison UI. Use two separate browser windows.
Generate approved fields locally, serialize once, persist before send, acknowledge only after durable server commit.
Identity comes from credentials/config, not an untrusted tenant selector.
Historical/reordered data can update charts but cannot make old sources look fresh.
Scenario inputs exercise normal processing; a button never directly creates a PASS verdict.
Only the demo source can execute the one simulated action. Production autonomous operations remain future work.

## Scope and differentiation

Keep two tenants, a small dependency graph, one detector, one simulation playbook, all eight scenarios and real evidence. Defer real regional hosting, advanced ML, real remediation, multiple playbooks and decorative UI complexity.

Our differentiator is inspectable evidence from local policy and outbound receipt to incident and recommendation. Do not claim the mandatory egress panel is invented here or that no competitor has similar capabilities. Body hashes prove matching bytes, not immutable audit history.

## Eight-hour milestones

0:30 contracts/ownership frozen; 2:00 first actual event on UI; 3:30 privacy/reliability/health proven; 5:00 minimal AIOps; 5:45 all scenarios integrated; 7:00 evidence and bug fixing; final hour clean start/rehearsal. This is aggressive; follow the cut-order rules rather than adding features.

## First steps for teammates

Read your [member guide](README.md), [contracts](.planning/CONTRACTS.md), [Git workflow](.planning/GIT_WORKFLOW.md) and [validation catalog](.planning/VALIDATION.md). Branch only after the planning revision reaches main. Work only in owned paths, update your status file, push small commits and request review. M1 merges reviewed slices.

Obtain actual organizer stream/format before certifying compatibility. Working target numbers are 10s p95 event-to-render, 15s breach-to-alert and 60s offline detection, pending organizer confirmation. Geographic residency is documented design, not a claim established by regional URLs.

## Current status

The adapter, verification code and dashboard are integrated. See [STATE.md](.planning/STATE.md) for acceptance results and the official input dependency.
