# Heimdal final audit

Audited on 2026-11-21 from `9dc77fe`. GSD's UAT scan found no standalone UAT or verification files. The audit used the eight phase summaries, the V00–V13 catalog, and the current code and live tests. It covered collector input, privacy, persistence and replay, HTTPS and tenant scope, health and timing, incident detection, remediation, scenario evidence, dashboard behavior, and startup instructions.

| Finding | Severity | Outcome |
|---|---|---|
| F-01 An interrupted run could stay marked Running | Medium | Expired results show Blocked until the collector supplies a final result. A verified HTTPS test covers expiry, late completion, tenant scope, and invalid timestamps. |
| F-02 Organizer input could imply health data the source never measured | Medium | The adapter preserves absent connectivity and availability fields and rejects boolean values as numeric measurements. |
| F-03 The restored README had outdated commands and claims | Medium | Corrected setup, certificate filenames, launch instructions, and release status. Preserved the teammate's banner and layout. |
| F-04 Mock scenario and transition data could remain visible on switching to live | Medium | The dashboard uses fresh view state on each mode switch. The Edge regression deliberately holds the live response while checking that fixture results disappear. |

## Release verification

- 61 Python checks passed with Edge enabled, including all eight live scenarios, durable outage replay, tenant switching, and remediation recovery and rollback. The frontend production build and all 15 UI checks passed.
- The synthetic run measured a 2.046-second p95 across 100 valid live browser samples, out of 102 eligible. Two were missing and none were clock flagged. The independent watchdog took 55.086 seconds. The injected packet loss check took 10.89 ms to persist an alert.
- Python dependency consistency, README and runbook links, the banner path, and the Python 3.11 grammar check passed. Runtime verification used Python 3.14 and Node 24 on Windows.

## Remaining limits

- V00 is blocked by the missing official organizer feed. Fixture coverage does not prove compatibility with that feed.
- Browser automation uses the actual Edge page and forwards requests through a CA-verified client. The [judge runbook](../docs/RUNBOOK.md) includes direct browser trust setup for the demo machine.
- Unpublished scenario results are in process memory. If the collector exits before reporting a result, the expired run is shown as blocked and can be retried.
- Frontend lint exits successfully with 10 existing React warnings. The audit avoids a broader refactor of the polling and rendering code.
- The prototype verifies assigned region scope on one host. Physical regional hosting is outside the tested deployment.
