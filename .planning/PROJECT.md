# Cicada: eight-hour prototype plan

See STATE.md for current implementation and validation progress.

## Objective and constraints

Build a two-tier observability web application. A customer-local Python collector keeps raw records and secrets local; an authenticated central service stores approved metadata and serves a React dashboard with health, anomalies, incidents, and recommendations.

The user's eight-hour limit supersedes the PDF's 24-hour event framing. Three people work in parallel; this is not 24 sequential development hours. All eight capability phases remain in scope, with smaller implementations and explicit acceptance gates.

## Team

- M1 uses GPT-6.2 Sol with high reasoning. Owns contracts, security, collector orchestration, persistence, SaaS, AIOps, remediation policy, and integration decisions.
- M2: teammate using the user's Gemini Flash setup. Owns React UI, typed client, browser timing and UI checks against frozen interfaces.
- M3: teammate using the user's Gemini Flash setup. Owns input adapters, deterministic demo source, scenario fixtures, local HTML presentation, black-box verification and runbook.
- Model labels describe user-selected tooling; no assumption about exact vendor model availability is needed.

Minimum demo: two tenants, a small pseudonymous dependency graph, one detector, all eight scenario behaviors, one simulated remediation playbook, a local proof page and a central dashboard.

## Stack

Python 3.11+, FastAPI/Uvicorn, Pydantic v2, HTTPX, aiosqlite/SQLite; React + TypeScript + Vite, plain CSS and simple SVG charts; pytest and focused browser checks. One SaaS process and one collector per demo tenant. Two-second HTTP polling, no WebSocket dependency. Freeze working versions and commit lockfiles during implementation. Check Vite's Node requirement; use compatible Node 22.12+ or newer supported release.

Real verified HTTPS on collector-to-SaaS traffic; lead-provisioned development CA/server certificates. Local inspector binds to loopback only. No Redis, Kafka, external LLM API, Kubernetes or proprietary cloud dependency.

## Claims and boundaries

Differentiate through inspectable evidence: incident -> contributing payload IDs -> SaaS receipt/digest -> exact local outbound bytes -> local policy decision. The required egress panel is not itself an originality claim. Hash matching is not tamper-proof history or proof of universal absence of leakage.

Implement approved metadata, local security summaries, persistent outbox, transactional deduplication, four health states, event-time trends, baseline anomalies, conservative correlation, explanations, and one approved reversible simulation.

Design/document only: real geographic regional deployments, backups/residency, horizontal scaling, production IAM. Defer complex ML, seasonal learning, real remediation, multiple playbooks, anchored audit history, SNMP/eBPF adapters and elaborate animations.

## Document authority

Actual evaluation PDF: judging source. REQUIREMENTS.md: sole requirement ID catalog. CONTRACTS.md: interfaces. ARCHITECTURE.md: trust boundary. TEAM_EXECUTION.md: ownership/time. Phase plans describe capability gates, not serial development. STATE.md records actual evidence.

PDF marks are 10/25/35/30; performance/reliability receives 10 of the 35 implementation marks. Working targets: 10s p95 event-to-render, 15s breach-to-alert, 60s offline detection. PDF numerical values await organizer confirmation. Organizer stream compatibility remains an external dependency until an actual organizer record is tested.
