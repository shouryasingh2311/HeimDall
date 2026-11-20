# Member 3 — adapters, simulation and verification using Gemini Flash

Branch feat/fixtures-validation. Own backend/collector/adapters/**, backend/collector/demo_source.py, backend/collector/static/**, backend/simulation/**, tests/scenarios/**, scripts/verification/**, docs/demo/** and status/MEMBER_3.md. Read contracts, architecture, validation and Git workflow. M1 owns daemon/local endpoint auth and core detector/storage.

## Execution queue across all eight phases

1. Phase 1: obtain organizer record/transport specification and preserve it as an authorized sample with no real credentials. Implement JSONL RawEvent adapter and later confirmed organizer protocol. Record unsupported fields/errors. Never claim organizer compatibility from custom samples.
2. Phase 2: secret fixtures (synthetic passwords/tokens/unknown nested fields), local HTML before/after view using escaped text. Include payload ID/digest/sent/ACK distinctions. Consume M1's loopback API with token/origin restrictions; do not create your own raw SaaS route.
3. Phase 3: black-box outage, lost ACK, process restart, duplicate and out-of-order tests. Collect expected IDs from durably accepted outbox records and compare with actual SaaS records. Test cap/backpressure with reduced local limits.
4. Phase 4: boundary cases for each health rule, stale source with fresh collector heartbeat, delayed old heartbeat, replay after outage, and offline delay. Run benchmark report with sample count, clocks and replay cohort.
5. Phase 5: seeded normal/drift/sustained-deviation, local auth bursts, dependency-related and unrelated simultaneous incidents. Fixtures feed RawEvent; do not call internal incident creation. Include warm-up and zero-variance cases.
6. Phase 6: pure DemoSource tick/inject/snapshot/restore/apply_scale helper. Memory demand/capacity produce metrics; restore previous capacity. M1 persists snapshots/commands. Verify telemetry changes after action and returns after rollback; no dashboard state mutation.
7. Phase 7: implement eight scenario input handlers and a verifier that polls actual evidence with bounded timeout. Return blocked if prerequisite absent, failed if assertion fails. Test scenarios individually and different orders; reset only demo inputs after pending queues/actions settle. Local verifier may inspect raw locally; central result contains only typed counters/IDs.
8. Phase 8: runbook, installation prerequisites, demo order, expected evidence, fallback disclosure and known limitations. Run a fresh startup rehearsal with teammates. Document real commands only after implementation exists.

## Local demo source scope

Four configured roles (load balancer, API, auth, DB) inside one dependency group plus an unrelated source control; two tenants for isolation. Use configured opaque IDs after M1 sanitizer. Two-second ticks, seeded bounded variation. Add disk/network/service signals per contract, no realistic-load simulator project.

For network scenario change inputs and service impact according to explicit simulated dependency. For outage use M1 FaultTransport wrapper, not stop generating data. For duplicates reuse original UUID/body at delivery layer. For replay retain original times. Scenario 8 targets demo source only, never organizer data.

## Task method and checks

One adapter, pure state helper, fixture set or black-box check per agent turn. Request explicit expected/observed data and timeouts. Never stub PASS. Do not fix core bugs in M1 paths; provide minimal reproducer and failing IDs. Avoid resetting databases as a workaround for failed deduplication.

Run pytest tests/scenarios and report individual V-check results; if core unavailable, mark blocked. Update status file every 30-45 min. Commit small owned slices, push normally, PR to main. M1 reviews input privacy and all evidence assertions.

## Agent task template

Implement [adapter/fixture/test] against CONTRACTS.md in owned paths only. Generate synthetic raw input locally, preserve identity/time, and assert real observed output. Do not create alerts directly, modify security rules, fake verdicts, overwrite contracts or access another member's files. Report run command, observed result and dependencies.
