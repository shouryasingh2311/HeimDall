# Acceptance catalog and judge evidence

Status: specification only. Checks below must be implemented/run during the build. Do not report them as passed now. M3 owns black-box harness; M1 owns core tests and correctness review; M2 owns browser checks.

## Evidence format

Record check_id, run_id, source mode (organizer/demo), commit SHA, start/end UTC, expected, observed, pass/fail/blocked, and safe artifact paths. Keep raw evidence local; committed/central reports use only approved synthetic-safe metadata, counters and IDs. Assertions inspect actual database/API/transport outcomes, not scenario handler's claimed status.

| Check | What must be demonstrated | Owner / collaborators |
|---|---|---|
| V00 | Actual organizer record/format ingested with identity/time preserved; malformed input visible; fallback clearly labelled | M3 / M1 |
| V01 | Separate processes; verified HTTPS; invalid token/CA/hostname rejected; startup instructions repeatable | M1 / M3 |
| V02 | Tenant A cannot inject/read/subscribe-to/action tenant B data; body/header/region/source mismatch denied; collector cannot approve action | M1 / M3 |
| V03 | Raw secrets local only; typed nested rejection; local inspector restricted; actual sent-body/received digest equality; retention purge | M1 / M3,M2 |
| V04 | Continued input during 30s outage; durable queue/retry; lost ACK; process restart; expected=received unique ID sets; no extra analytic effects; cap/backpressure visible | M1 / M3 |
| V05 | All health boundaries, severity precedence, missing metrics, config invalid, live heartbeat/stale source, stale replay; reasons/history; offline <=60s | M1 / M3,M2 |
| V06 | Four failures do not trigger; five within 10s trigger; spaced failures do not; duplicate raw input not recounted; no raw auth egress | M1 / M3 |
| V07 | Network latency/loss and configured downstream service impact; source/severity/trend; alert created <=15s from injected condition | M1 / M3,M2 |
| V08 | Warm-up, sigma floor, benign spike, sustained and below-static-threshold anomaly; per-source/tenant separation; related merge/unrelated separation; reproducible explanation and score | M1 / M3,M2 |
| V09 | Same UUID/body retries and concurrent duplicates produce one record/effect; different bytes conflict; out-of-order chart sorted; stale event cannot overwrite current state | M1 / M3 |
| V10 | Actual first-visible-render timing; alert and offline timings; sample counts/cohorts/clock assumptions; no fake timestamps or hidden replay exclusions | M2 / M1,M3 |
| V11 | Proposal/policy/real operator approval; queued execution; persisted idempotent demo state/snapshot; recovery telemetry; rollback telemetry; duplicate/restart/wrong-role tests | M1 / M3,M2 |
| V12 | All eight scenarios individually and varied order; observed verdicts; honest errors/blocked states; live frontend build; tenant cache clear; clean startup | M3 / M2,M1 |
| V13 | Architecture/trust-boundary walkthrough, assigned-region enforcement versus geographic limitation, scaling explanation and known gaps | M1 / M3 |

## Scenario mapping

1 secret -> V03; 2 SaaS connectivity loss -> V04; 3 failed logins -> V06; 4 network degradation -> V07; 5 CPU/memory anomaly -> V08; 6 related alert storm -> V08; 7 duplicates/out-of-order -> V09; 8 remediation -> V11.
Additional mandatory checks include V00/V01/V02/V05/V10, not just eight buttons.

## Timing protocol

Use organizer live stream if supplied. Preserve source timestamps. On one demo host clocks share OS clock; across hosts measure/synchronize offsets and disclose uncertainty. Record actual run mode. Historical replay is not a passing real-time benchmark.

Warm-up minimum ten eligible samples for detector. Collect at least 100 actually rendered normal live events when practical; report exact count even if lower. p95 = sorted latency at ceil(0.95*n), not average. Compute each payload's first visible render once per session/run; exclude unopened/background UI measurements only under an explicit recorded cohort rule. Show missing render receipts, sample selection and all-event/replay summaries. Never omit slow samples just to pass.

Outage scenario lasts 30s and proves buffering, not necessarily offline status. Separate offline test stops fresh heartbeats >=65s and measures actual Poor transition <=60s; design threshold55s/watchdog1s provides margin. Alert timing starts at injected threshold breach, not when correlator decides an incident exists.

## Targeted command plan

Once code and manifests exist, the owners should provide working equivalents of:

    python -m pytest tests/core
    python -m pytest tests/scenarios
    npm --prefix frontend ci
    npm --prefix frontend run build

These commands are future acceptance targets, not commands executed successfully in the documentation revision. Add focused browser tests for timing/error/cache behavior; avoid tests that merely assert component names. Prefer disk-backed temporary DBs for restart tests. Build/test nonzero exits block merge; no error-swallowing fallback.

## Judge demo (about five minutes, adjust to organizer)

1. State customer problem and show local/central boundary and two tenant credentials.
2. Inject synthetic secret locally; show exact outbound receipt match with only metadata centrally.
3. Trigger network outage while generation continues; show queue and later ID-set reconciliation.
4. Show baseline deviation and related incident, then an unrelated control; explain evidence/likely cause.
5. Propose approved demo scaling, show collector result and fresh recovery telemetry; rollback.
6. Show actual render/alert/offline timing reports and disclose stream/residency/ML limitations.

All eight checks must be runnable even if live presentation highlights only some. Pre-recorded pass/fail screenshots are not substitutes for working state.
