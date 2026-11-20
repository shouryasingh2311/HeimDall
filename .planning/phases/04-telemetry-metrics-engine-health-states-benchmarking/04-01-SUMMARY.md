# Phase 4 verification

The SaaS evaluates four health states with configurable thresholds and expected signals. An independent watchdog expires collector heartbeats and source telemetry. State changes persist with UTC timestamps and reasons. Late telemetry remains available in history, and trend charts show gaps for absent values.

| Check | Observed evidence |
|---|---|
| V05 | Health boundaries, missing signals, severity precedence, invalid configuration, stale replay, tenant isolation and recovery passed. |
| V07 health | Injected 10% packet loss moved a live source to Poor and recorded `packet_loss` in the transition history. Dependency correlation and persisted alerts require Phase 5. |
| V10 offline | The recorded transition occurred 55.351 seconds after the last verified heartbeat. No fleet requests were made during the 65-second interruption. |
| V10 render | Edge recorded 100 live samples from 115 eligible synthetic records. p95 was 842 ms. The remaining 15 were missing render receipts, and zero were flagged for clock ordering. Browser and producer ran on the same machine. |

Render benchmarks show all eligible counts as well as live and replay or delayed cohorts. The final organizer-stream rehearsal and alert creation timing remain open.
