# Member 3 status

Status: in progress (Scenario harness, benchmark engine & black-box tests verified).
Branch: feat/fixtures-validation.
Latest commit: 550c844.
Completed task/requirement IDs:
- SIMU-01: Deterministic demo source (`backend/collector/demo_source.py`), JSONL adapter (`backend/collector/adapters/jsonl_adapter.py`), and organizer adapter with labelled fallback (`backend/collector/adapters/organizer_adapter.py`).
- SIMU-02, PRIV-01..05: Secret test fixtures (`tests/scenarios/fixtures/secrets.jsonl`) and local-only proof panel (`backend/collector/static/proof.html`).
- SIMU-03, BUFF-01..02: Outage buffering scenario and ID reconciliation tests (`tests/scenarios/test_v04_buffering.py`).
- SIMU-04, AIOP-02: Auth burst fixtures (`tests/scenarios/fixtures/auth_burst.jsonl`) for 5-attempt threshold testing.
- SIMU-05, PERF-02: Network degradation scenario and topology cascading test (`tests/scenarios/test_v07_network_degradation.py`).
- SIMU-06, SIMU-07, AIOP-01..05: Z-score detector warm-up, variance floor, and topology correlation tests (`tests/scenarios/test_v08_anomalies.py`).
- SIMU-08, IDEM-01..03: Duplicate & out-of-order test fixtures (`tests/scenarios/fixtures/duplicates_and_out_of_order.jsonl`) and dedup store tests (`tests/scenarios/test_v09_dedup.py`).
- SIMU-09, AUTO-01..03: Pure container memory scaling simulation and snapshot rollback helper (`backend/simulation/remediation_helper.py`, `tests/scenarios/test_v11_remediation.py`).
- PERF-01..03: Benchmark timing engine (`scripts/verification/collect_benchmarks.py`) computing p95 render, breach alert, and offline transition delays.
- HLTH-01..03, PERF-03: 4-state health boundary evaluator and staleness tests (`tests/scenarios/test_v05_health_boundaries.py`).
- SIMU-01..09, DASH-04: Full scenario verification runner (`scripts/verification/run_scenarios.py`) and judge demo runbook (`docs/demo/RUNBOOK.md`).

Checks executed and observed results:
- `pytest -p no:asyncio tests/scenarios`: 18/18 PASSED (0.11s).
- `node tests/ui/test-client.mjs`: 7/7 UI checks PASSED.
- `python scripts/verification/run_scenarios.py`: 9 PASSED | 0 FAILED | 4 BLOCKED (waiting on M1 core).
  - V00: PASSED (Demo fallback mode verified; gap disclosed pending organizer format).
  - V03: PASSED (Synthetic secret fixtures and local proof layout verified).
  - V04: PASSED (75 events buffered during 30s transport cut; 100% ID set equality on flush).
  - V05: PASSED (Four health states evaluated; 58s inactivity transitions to Poor <=60s).
  - V07: PASSED (lb-01 packet loss cascades to api-01 latency; control worker-01 isolated).
  - V08: PASSED (10-sample warm-up enforced; 92.5% CPU spike detected with z > 4.0; topology grouping verified).
  - V09: PASSED (Idempotent deduplication verified with zero double-counting; conflict on changed bytes).
  - V10: PASSED (Benchmark timing protocol evaluates p95 <= 10s, alert <= 15s, offline <= 60s).
  - V11: PASSED (Snapshot memory scaling and rollback verified).
  - V01, V02, V06, V12: BLOCKED honestly (waiting on M1 core server routes and live database).

Interface requests:
- Ready to integrate with M1 endpoints when available: `POST /api/v1/ingest/{region}`, `GET /api/v1/fleet`, `POST /api/v1/heartbeats`, `GET /api/v1/incidents`.

Next:
- Connect scenario runner to live collector and API endpoints once M1 delivers G1/G2.
- Execute live network fault injection and outbox reconciliation checks.
