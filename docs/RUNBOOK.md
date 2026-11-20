# Judge Evaluation and Live Scenario Runbook

Procedures for evaluating, running, and verifying the Heimdal observability platform during live review.

---

## 1. Start the live demo

Build the dashboard once. Stop existing demo processes using ports 8443 or 9001. Use separate PowerShell terminals for SaaS and the collector. Run the bootstrap command once for a new runtime.

    npm --prefix frontend run build
    .venv/Scripts/python -m scripts.security.bootstrap --runtime .heimdal/scenario-demo
    .venv/Scripts/python -m backend.saas.main --runtime .heimdal/scenario-demo --dashboard frontend/dist
    .venv/Scripts/python -m backend.collector.daemon --runtime .heimdal/scenario-demo --scenarios

Open the loopback runner at http://localhost:9001/scenarios and enter the local token from `.heimdal/scenario-demo/collector-alpha.json`. Open the operator dashboard at https://localhost:8443 and enter the credentials from `.heimdal/scenario-demo/operator-alpha.json`. See [local HTTPS setup](PHASE1.md) if the browser does not trust the development CA.

## 2. Run the eight CICADA scenarios

Start one scenario at a time on the local page and watch **Scenario Verification** in the dashboard. The dashboard reads the latest observed result for each scenario.

| Scenario | What to show |
|---|---|
| 1. Local secret handling | Match the payload digest in the local audit and SaaS. The seeded secret is absent from the committed body. |
| 2. Outage buffering | Metadata sends pause for 30 seconds while the collector queues 75 events. Its verifier checks central absence during the pause and reconciles UUIDs and digests after delivery resumes. |
| 3. Failed logins | The first four inputs produce no summary. The fifth produces a typed count and a pseudonymous origin. |
| 4. Network degradation | The generated latency and packet loss produce related alerts. The verifier records whether the alerts appear within 15 seconds. |
| 5. Sustained CPU anomaly | Show the rolling baseline, the single-spike control, and the alert after two consecutive deviations. |
| 6. Alert correlation | Two related source alerts share an incident. The worker's alert has a separate incident. |
| 7. Duplicate and late delivery | The identical body returns a duplicate receipt. The older event is retained as historical. |
| 8. Simulated remediation | In the incident tab, request a proposal for the memory incident and approve it. Wait for fresh recovery telemetry and incident resolution, then roll back the original action. The runner waits for these observed outcomes, up to three minutes. |

Use **Reset demo inputs** after pending work settles. It preserves stored evidence, deduplication, and the action audit. Repeating a scenario generates new legitimate payload IDs.

The CLI reads the real SaaS results and reports missing evidence as blocked.

    .venv/Scripts/python -m scripts.verification.run_scenarios --runtime .heimdal/scenario-demo --json

The default scenario source is synthetic. V00 remains blocked until the official organizer stream is verified. Use the standalone offline watchdog test for the heartbeat requirement. The metadata outage scenario keeps heartbeats running.

## 3. Real-Time Performance Benchmarking Protocol

Open **Measured render timing** on the fleet page while sources are visible. The dashboard shows committed observations and reports missing or clock-flagged samples.
* Collection-to-dashboard latency (p95): evaluates `rendered_at_utc` (captured via `requestAnimationFrame` in React) minus `event_time_utc` (target: $\le 10\text{s}$).
* Breach-to-alert latency: evaluates alert record creation timestamp minus fault injection timestamp (target: $\le 15\text{s}$).
* Offline detection delay: evaluates transition to `Poor` timestamp minus heartbeat termination timestamp (target: $\le 60\text{s}$).

---

## 4. Evaluation Q&A Reference Guide

### Q1: Exactly what data leaves the local environment, and what stays behind?
> Raw log text, original payloads, unredacted syslog lines, passwords, API tokens, usernames, and real IP addresses stay strictly on the local collector host. Only strongly-typed Pydantic metadata leaves: normalized metrics (0 to 100 floats), UTC event timestamps, HMAC pseudonymous source IDs, health status tokens, and aggregated threat summaries.

### Q2: How do you prove that secrets were not sent?
> The local proof panel at `http://localhost:9001/audit` shows the exact outbound JSON for inspection. Matching its SHA-256 digest with the SaaS receipt confirms that the inspected bytes match the received bytes.

### Q3: What happens when SaaS is unreachable?
> The collector commits approved events to a disk-backed outbox before sending. Retries use exponential backoff and stable payload IDs. In the tested outage, every queued ID and digest matched the committed SaaS evidence after replay.

### Q4: How does your AIOps distinguish real anomalies from normal spikes?
> The rolling detector warms up on ten samples and needs two consecutive positive z-scores above 3. Fixed severe thresholds can trigger immediately.

### Q5: What safeguards exist before automated remediation executes?
> Heimdal enforces human-in-the-loop authorization. Actions require operator role authentication, can only target pre-approved demo targets, are rate-limited to 3 per hour, capture an atomic state snapshot before modification, and support single-click rollback.
