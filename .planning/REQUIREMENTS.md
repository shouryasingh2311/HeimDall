# Requirements and traceability

Canonical requirement IDs. All entries are planned, not completed. M1=lead/core, M2=dashboard, M3=input/verification. See VALIDATION.md for evidence checks.

| ID | Required behavior | Phase | Accountable owner | Evidence |
|---|---|---:|---|---|
| ARCH-01 | Separate customer collector and central metadata service | 1 | M1 | V01,V03 |
| ARCH-02 | Collector credentials with verified TLS and invalid-certificate rejection | 1 | M1 | V01 |
| ARCH-03 | Tenant isolation for queries, storage, analytics and actions | 1 | M1 | V02 |
| ARCH-04 | Assigned-region enforcement; document geographic deployment separately | 1 | M1 | V02,V13 |
| PRIV-01 | Raw records stay local; construct approved metadata before any egress | 2 | M1 | V03 |
| PRIV-02 | Typed nested allow-list; reject unknown keys and invalid metric values | 2 | M1 | V03 |
| PRIV-03 | Local regex fixture catalog plus default-drop raw text | 2 | M1 | V03 |
| PRIV-04 | Persistent tenant-local pseudonyms, private lookup where needed | 2 | M1 | V03 |
| PRIV-05 | Loopback raw/outbound proof with actual bytes, payload ID and receipt matching | 2 | M1 | V03 |
| BUFF-01 | Persist every event before first send; bounded durable outbox | 3 | M1 | V04 |
| BUFF-02 | Backoff/reconnect; delete only committed acknowledged IDs | 3 | M1 | V04 |
| IDEM-01 | Stable input identity and UUID across retry/restart | 3 | M1 | V04,V09 |
| IDEM-02 | Transactional persistent deduplication including analytic side effects | 3 | M1 | V04,V09 |
| IDEM-03 | UTC/timezone, event-time trends and explicit late-event policy | 3 | M1 | V09 |
| METR-01 | CPU, memory, disk usage/I/O, network rates, latency/loss, service availability and connectivity | 4 | M1 | V05,V07 |
| METR-02 | Collector status, fresh heartbeat, version/resources/backlog/config status | 4 | M1 | V05 |
| HLTH-01 | Complete configurable four-state rules with severity precedence | 4 | M1 | V05 |
| HLTH-02 | Staleness degrades health; late replay cannot refresh current state | 4 | M1 | V05 |
| HLTH-03 | UTC transition history with reasons | 4 | M1 | V05 |
| PERF-01 | First dashboard render minus organizer event time p95 <=10s working target | 4 | M2 | V10 |
| PERF-02 | Injected breach to persisted alert <=15s working target | 4 | M1 | V07,V10 |
| PERF-03 | Offline detection <=60s including watchdog scheduling | 4 | M1 | V05,V10 |
| AIOP-01 | Per-tenant/source/metric rolling statistical detector with warm-up/variance floor | 5 | M1 | V08 |
| AIOP-02 | Local failed-login detection exports typed summary only | 5 | M1 | V06 |
| AIOP-03 | Time plus configured dependency correlation; preserve unrelated incidents | 5 | M1 | V08 |
| AIOP-04 | Evidence-backed likely cause and service impact, no causal certainty | 5 | M1 | V07,V08 |
| AIOP-05 | Observed/baseline values, event IDs and explicit heuristic evidence score | 5 | M1 | V08 |
| AUTO-01 | One SCALE_CONTAINER_MEMORY proposal for demo targets only | 6 | M1 | V11 |
| AUTO-02 | Operator approval, tenant checks and idempotent collector command dispatch | 6 | M1 | V02,V11 |
| AUTO-03 | Persistent application audit, snapshot rollback and telemetry proof | 6 | M1 | V11 |
| SIMU-01 | Actual organizer adapter plus labelled deterministic fallback | 7 | M3 | V00 |
| SIMU-02 | Secret-in-log scenario via raw input and receipt inspection | 7 | M3 | V03 |
| SIMU-03 | Transport outage scenario with real outbox/recovery evidence | 7 | M3 | V04 |
| SIMU-04 | Failed-login inputs exercise local analyzer | 7 | M3 | V06 |
| SIMU-05 | Network degradation demonstrates source/service impact | 7 | M3 | V07 |
| SIMU-06 | Baseline deviation plus normal controls exercise detector | 7 | M3 | V08 |
| SIMU-07 | Related/unrelated alert storm exercises correlator | 7 | M3 | V08 |
| SIMU-08 | Duplicate, out-of-order and stale events exercise storage/current state | 7 | M3 | V09 |
| SIMU-09 | Approval/action/rollback changes actual demo source and fresh telemetry | 7 | M3 | V11 |
| DASH-01 | Live fleet, trends, reasons, collector metadata, incidents and timing | 8 | M2 | V05,V10,V12 |
| DASH-02 | Separate local/SaaS views matched by ID/digest, no raw bridge | 8 | M2 | V03,V12 |
| DASH-03 | Incident evidence and approval/rollback status controls | 8 | M2 | V08,V11,V12 |
| DASH-04 | All eight local runner controls and safe observed-result display | 8 | M2 | V12 |

## Completion rules

43 v1 requirements, all mapped. Coverage is not implementation evidence. All eight phases require acceptance; no production claim. Actual organizer input and final target values remain kickoff dependencies. Regional deployment is design-only; single-host region policy is an explicit limitation. Keep old IDs stable; this file supersedes the former PROJECT.md ID meanings.
