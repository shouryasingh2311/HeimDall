# Three-member execution plan: eight hours

## Allocation principle

M1 uses GPT-6.2 Sol with high reasoning and owns architecture, security, reliability and AIOps. M2 uses Gemini Flash for UI work against the shared contracts. M3 uses Gemini Flash for deterministic inputs, simulation helpers, local presentation and verification.

The lead is the critical path. Use the minimal scope below; if the lead slips, teammates take mechanical tests/fixtures/documentation, never redesign authentication or storage. team-config.json records this workflow; legacy config.json is retained only for optional GSD tooling compatibility and does not govern team branching.

## All-phase responsibility map

A = accountable implementation/acceptance owner. Contributors have explicit artifacts.

| Phase | M1: core owner | M2: bounded UI contribution | M3: bounded input/verification contribution |
|---|---|---|---|
| 1 Architecture/transport | A: shared schema, credentials, TLS, API/storage startup | Scaffold React/Vite, typed API client, connection states | Organizer sample inventory, JSONL adapter, clean-run checklist |
| 2 Privacy/proof | A: sanitizer, HMAC, strict schema, loopback server, egress bytes | SaaS receipt/digest inspector; no raw fetch | Local HTML proof layout, secret fixtures, retention assertions |
| 3 Buffer/dedup | A: outbox, retries, transaction/uniqueness, ACK, late policy | Queue/replay/receipt indicators from API | Outage/ACK-loss/restart/reorder tests and ID reconciliation |
| 4 Health/performance | A: health rules, heartbeat, watchdog, server clocks | Fleet/trends/transitions, first-render timing | Boundary/freshness fixtures, latency/clock report |
| 5 AIOps | A: detector, local security, topology correlation, explanations | Signal table, baseline chart, likely-cause evidence | Normal/anomaly/auth/related/unrelated controlled inputs |
| 6 Safe simulation | A: proposal/policy/approval/audit/idempotent command path | Approval/rollback UX, pending/failure states | Pure demo state, snapshot/restore, subsequent recovery samples |
| 7 Scenarios | Wire real collector/fault interfaces; review verdict correctness | Safe scenario result cards and link/instructions to local runner | A: eight input scenarios, verifier, reset, evidence artifacts |
| 8 Dashboard/demo | API/static serving integration; final technical review | A: complete live dashboard and browser checks | Runbook, limitations, demo script and acceptance rehearsal |

## File ownership during implementation

- M1: backend/shared/**, backend/collector/** EXCEPT adapters/**, demo_source.py, static/**; backend/saas/**; pyproject.toml/backend lockfile; scripts/security/**; tests/core/**; .planning/CONTRACTS.md; .planning/STATE.md; root architecture decisions.
- M2: frontend/** (including package.json and lockfile), tests/ui/**, .planning/status/MEMBER_2.md.
- M3: backend/collector/adapters/**, backend/collector/demo_source.py, backend/collector/static/**, backend/simulation/**, tests/scenarios/**, scripts/verification/**, docs/demo/**, .planning/status/MEMBER_3.md.
- M1 also owns .planning/status/MEMBER_1.md. Changes to another owner's path require a handoff agreed with that owner. M3 tests may expose core defects; M1 fixes core.
- Shared application entry points, schema, API routes and database migrations are exclusively M1. No concurrent root-file scaffolding.

## Timeline and gates

| Elapsed | M1 | M2 | M3 | Gate |
|---|---|---|---|---|
| 0:00-0:30 | Freeze contracts, repo/startup/TLS plan, identities | Confirm screens/types, create UI branch | Obtain organizer sample/format, create fixture branch | G0 contract and owner agreement |
| 0:30-2:00 | Minimal verified ingest, sanitizer, DB, local endpoint; publish fixtures | Scaffold/client/fleet shell with labelled mocks then live route | JSONL/demo source, local HTML, fixture catalog | G1 one raw input -> safe persisted record -> visible UI |
| 2:00-3:30 | Durable outbox/dedup, heartbeat/health, collector auth summary | Live fleet/trend/receipts, render timing | Outage/restart/reorder and health boundary tests | G2 privacy/reliability/health proven |
| 3:30-5:00 | Minimal rolling detector, conservative correlation and explanations | Incident evidence UI and scenario results | Normal/anomaly/auth/topology fixtures, verifier | G3 anomaly + correlation + local auth work |
| 5:00-5:45 | One proposal/approval/collector simulation/rollback path | Approval/rollback pending/error UI | Snapshot helper and recovery/rollback verification | G4 all eight scenario behaviors integrated |
| 5:45-7:00 | Fix core defects; merge tested increments | Browser/build/real render validation | Run V00-V13 and independent scenario order | G5 evidence complete or explicit failure recorded |
| 7:00-8:00 | Feature freeze, final acceptance, technical demo | Presentation polish only, verify live mode | Fresh start/rehearsal, release notes/limitations | G6 repeatable demo |

This is an aggressive prototype budget, not a guarantee. All members continue useful owned work while an interface is pending. Contract fixtures are for UI development only; never judge evidence.

## Cut order and escalation

At G1 failure: M2/M3 stop optional styling/generator realism and help isolate transport/contract defects. At G2 failure: M1 suspends extra metrics polish and keeps the four-node/two-tenant fixture scope. At G3 failure: use the single specified detector and one configured dependency group; remove optional charts. At G4 failure: stop adding features and fix the minimal approved simulation path, never pretend it passed.

Cut first: themes/animations, WebSockets (already excluded), multiple remediation actions, extra connectors, cloud deployment, sophisticated scoring, arbitrary topology discovery. Keep all eight capability phases and scenario behaviors. One local runner is sufficient; central remote scenario triggering is not required. Do not cut TLS, tenant denial checks, organizer compatibility disclosure, raw-data boundary, ID reconciliation, genuine render timing or honest failures.

## Coordination

Every 30-45 minutes update own status file: commit SHA, completed IDs/checks, interface needs, next task, blocker. Provide a small commit/PR after each runnable slice. Only M1 integrates into main. No merge of feature branches directly into one another. M2/M3 pull reviewed main at integration gates. Read GIT_WORKFLOW.md and individual MEMBER files before implementation.
