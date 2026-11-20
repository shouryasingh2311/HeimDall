# Member 1 — lead using GPT-6 Astra

Read PROJECT_OVERVIEW.md, ARCHITECTURE.md, CONTRACTS.md, TEAM_EXECUTION.md, GIT_WORKFLOW.md, VALIDATION.md and all eight phase plans. Branch feat/core-platform. You own the hard work and final integration; M2/M3 do not independently implement security or analytic policy.

## Execution queue

1. G0 / phase 1: freeze models/endpoints/units, select working pinned dependencies, create backend manifest/lockfile and ignore rules, tenant/role config, TLS development trust setup and minimal SQLite/API startup. Export safe fixtures to teammates. Accept M3's input through the RawEvent adapter interface.
2. G1 / phases 1-2-8: implement local typed sanitizer, HMAC mapping, exact-byte outbox entry shape, verified transport, tenant-bound ingestion, receipt/read routes, loopback raw inspector endpoints and static UI wiring. Get one actual input into the UI; M2/M3 supply presentation.
3. G2 / phases 3-4: persist-before-send queue, ACK/conflict rules, bounded retry/backpressure, persistent unique ingest and analytic identities. Build fresh-heartbeat loop, complete health precedence, transition history and late-event/current-state policy. Integrate local >=5 failed-logins/10s summary. Review M3's crash/ACK-loss tests.
4. G3 / phase 5: implement only the specified rolling baseline, per-series isolation, configured dependency grouping, alert deduplication and evidence templates. Expose likely cause and transparent heuristic score. Check unrelated incidents are not merged. Persist/rebuild state coherently.
5. G4 / phase 6: one demo-only memory scaling proposal, operator role/policy checks, persistent audit/lifecycle, outbound collector command polling, atomic snapshot/state/receipt and rollback. M3 supplies pure simulation helper; you own its authorization and persistence wrapper. M2 supplies controls.
6. Phase 7: wire fault-injection wrapper in demo mode, source adapter, local runner routes and safe verification results; M3 supplies scenario inputs/assertions. A scenario trigger must not directly synthesize SaaS incidents or verdicts.
7. Phase 8 / G5-G6: serve built UI, validate genuine render receipts, inspect cross-tenant/invalid TLS/late replay behavior, review evidence, merge fixes and conduct clean start.

## Mandatory technical decisions

Use CONTRACTS.md without independent alternatives. One async writer/transaction boundary per process. No in-memory-only ingest or dedup state. Do not mutate analytic caches before successful commit. Do not export raw diagnostics as errors. Real organizer mode disables demo actions; explain that simulation is a separate safe target.

Every security-sensitive contribution from another member needs your review. Ask M2/M3 for small pure fixtures/tests/docs if overloaded; preserve ownership of core decisions.

## Completion handoffs

At each gate push a small core commit/PR, post accepted API version and commit SHA in status/MEMBER_1.md, and merge only tested slices. Supply an actual example of Fleet, IncidentDetail, IngestReceipt, proposal state and ScenarioResult before asking M2 to wire each screen. Integration status belongs in STATE.md.

## Agent task template

Implement only the current named task on feat/core-platform. Read the contracts and relevant phase plan first. Do not add services or change the metadata boundary. Add the targeted behavioral test, run it, report changed files, requirement IDs and remaining risk. Keep teammate-owned files untouched unless an explicit handoff has been agreed.
