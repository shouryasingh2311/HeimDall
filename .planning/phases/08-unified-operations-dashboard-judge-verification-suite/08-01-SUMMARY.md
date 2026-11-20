# Phase 8 release verification

The release integrates the production React build on the same HTTPS origin as the SaaS API. It serves the build's favicon and revalidates its entry page. API responses direct browsers and intermediaries to avoid caching tenant data when operators switch credentials. The two UI clocks previously using local time now display UTC.

The initial rehearsal exposed a Scenario 8 interaction with prior normal traffic. Scaling lowered simulated memory pressure from about 98% to about 65%, but a warm ordinary baseline near 45% flagged the healthy simulation samples. Simulated metrics now use separate rolling baselines. The regression warms the normal series before exercising genuine approval, recovery, restart and rollback.

## Evidence

Run on 2026-11-20 with temporary runtimes, generated certificates, Edge, and synthetic input on one Windows host. Base `c787911`, with the Phase 8 changes in this revision. The locked npm installation, production build, 60 Python checks and 15 UI checks passed. The Python checks include the browser-enabled suites and the full live scenario rehearsal.

| Check | Observed result |
|---|---|
| V00 | Blocked pending organizer input. The labelled synthetic fallback and adapter tests passed. |
| V01 | Separate collector and SaaS processes exchanged metadata over CA and hostname verified HTTPS. Untrusted CA, hostname mismatch and invalid credentials were rejected. |
| V02 | The role matrix denied unauthorized access. Cross-tenant ingest, reads and actions were rejected. Switching Alpha → Beta → Alpha in Edge cleared and restored the correct scenario results. |
| V03 | The loopback-only audit and SaaS receipt matched on payload ID and digest. Invalid nested fields and the synthetic secret stayed out of central data. |
| V04 | The metadata pause reconciled 75 payload IDs and digests after 30 seconds. Separate checks covered backlog capacity, lost ACK and collector restart. |
| V05 | Health boundaries, precedence, stale replay and recovery passed. Watchdog marked the collector Poor after 55.095 seconds from the last accepted heartbeat. |
| V06 | Four failures and five spaced failures stayed local. Five failures within the window produced one typed alert. |
| V07 | Network and dependency alerts met the 15-second deadline. The separate injected-loss sample took 9.97 ms to persist an alert. |
| V08 | Tested warm-up, variance floors, single-spike control, sustained deviation, explanation evidence and separation of related and unrelated events. |
| V09 | Identical bytes produced one accepted effect, changed bytes conflicted, and late events were historical. |
| V10 | Browser p95 was 1.938 seconds for 100 valid live samples out of 105 eligible. Five had no render receipt and none were clock flagged. Separate tests covered historical, delayed and clock-flagged receipts. Browser and services shared the host clock. |
| V11 | Observed 96.97% memory before scaling, 64.65% after scaling, 64.30% after restart and 99.21% after rollback. Policy, quota, idempotence and audit checks passed. |
| V12 | All eight scenarios passed on the same live runtime in a mixed order, including reset and repeat. The built Edge dashboard showed 8/8 from stored results and the live CLI agreed. |
| V13 | The walkthrough shows the metadata trust boundary, regional credential checks and the one-process SQLite design. Geographic deployment and organizer compatibility remain unverified. |

In a separate clean Edge rehearsal, the loopback button launched Scenario 8. The UI displayed UTC with the browser set to Asia/Kolkata, and the operator requested, approved and rolled back the action. The loopback runner showed a pass and the SaaS dashboard showed 1/8 in that fresh runtime.

The browser tests render the actual dashboard and forward requests through a CA-verified test client. The [judge runbook](../../../docs/RUNBOOK.md) includes the direct browser trust setup, all eight controls, the benchmark instructions and the full regression command.
