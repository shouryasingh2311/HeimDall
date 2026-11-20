# Judge Evaluation and Live Scenario Runbook

Procedures for evaluating, running, and verifying the Heimdal observability platform during live review.

---

## 1. Start the live demo on Windows

1. Open PowerShell in the repository folder and run the [setup commands](../README.md#getting-started--local-setup). Stop any older Heimdal processes with **Ctrl+C** in their terminals so ports 8443 and 9001 are free.
2. Generate a fresh runtime once. Reuse it for restarts, or choose a new directory for a clean slate. Use the same directory in every command.

       .venv/Scripts/python -m scripts.security.bootstrap --runtime .heimdal/scenario-demo

3. To open the dashboard in Edge, trust the development CA you just generated for this Windows user. If prompted, check that the certificate belongs to your own Heimdal run before accepting it. Restart Edge if it was open. Remove that certificate from **Manage user certificates → Trusted Root Certification Authorities → Certificates** after the demo.

       certutil.exe -user -addstore Root .heimdal/scenario-demo/ca.pem

4. In the first terminal, start SaaS. In a second terminal in the same folder, start the collector. Leave both running.

       # Terminal 1
       .venv/Scripts/python -m backend.saas.main --runtime .heimdal/scenario-demo --dashboard frontend/dist
       # Terminal 2
       .venv/Scripts/python -m backend.collector.daemon --runtime .heimdal/scenario-demo --scenarios

5. Open <https://localhost:8443>. Open `.heimdal/scenario-demo/operator-alpha.json` locally and enter its `tenant_id` and `token`. Click **Connect dashboard** and check that **Fleet & Health State** populates.
6. In a separate browser window, open <http://localhost:9001/scenarios>. Use the `local_token` in `.heimdal/scenario-demo/collector-alpha.json`. Keep the JSON files and tokens off the projected screen.

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
| 8. Simulated remediation | Open **AIOps Incidents & Remediation** and select the incident with the memory signal. Click **Request Remediation Proposal**, then **Approve Remediation**. Wait for **Resolved** and fresh memory samples below 70%, then click **Rollback to Snapshot** on that same incident. The runner waits for evidence for up to three minutes. |

For Scenario 1, copy its payload UUID from the local runner. Open <http://localhost:9001/audit> with the same local token. Paste the UUID and click **Fetch local evidence**. In the SaaS **Payload Egress Inspector**, paste the UUID and click **Inspect Metadata**. Paste the local SHA-256 digest to see **DIGEST MATCH CONFIRMED**.

Use **Reset demo inputs** after pending work settles. It preserves stored evidence, deduplication, and the action audit. Repeating a scenario generates new legitimate payload IDs.

The CLI reads the real SaaS results and reports missing evidence as blocked.

    .venv/Scripts/python -m scripts.verification.run_scenarios --runtime .heimdal/scenario-demo

The default scenario source is synthetic. V00 remains blocked until the official organizer stream is verified. Use the standalone offline watchdog test for the heartbeat requirement. The metadata outage scenario keeps heartbeats running.

## 3. Check tenant isolation and timing

Switch the dashboard to the credentials from `operator-beta.json`. **Scenario Verification** should show no Alpha results. Switch back to Alpha and its results should reappear.

Open **Measured render timing** on the fleet page while sources are visible. The dashboard shows committed observations and reports missing or clock-flagged samples.
* Collection-to-dashboard latency (p95): evaluates `rendered_at_utc` (captured via `requestAnimationFrame` in React) minus `event_time_utc` (target: $\le 10\text{s}$).
* Breach-to-alert latency: evaluates alert record creation timestamp minus fault injection timestamp (target: $\le 15\text{s}$).
* Offline detection delay: evaluates transition to `Poor` timestamp minus the last accepted heartbeat timestamp (target: $\le 60\text{s}$).

For an offline demo, stop the collector with **Ctrl+C** after all scenarios finish. Leave SaaS up, wait about 56 seconds, and look for **Poor** and the heartbeat expiration reason. Restart the collector with the same runtime to see it recover. The benchmark window covers the last five minutes. Keep the dashboard visible while measuring, and run the producer, SaaS and browser on one machine for a shared clock.

## 4. Run the automated checks for Phases 1–8

From a separate PowerShell terminal in the repository folder, build the dashboard first. The Python suite starts its own services on temporary ports with its own certificates and databases.

    npm --prefix frontend run build
    npm --prefix frontend test
    $env:HEIMDAL_TEST_DASHBOARD = 'frontend/dist'
    $env:HEIMDAL_TEST_BROWSER = 'msedge'
    .venv/Scripts/python -m pytest -q -s

On Windows, this uses the installed Edge browser. Browser tests run real page interactions with requests forwarded through a CA-verified test client. The manual demo above exercises direct browser trust. The automated checks cover the complete demo path on synthetic input. Physical multi-region hosting and organizer compatibility need their own environments.

---

## 5. Evaluation Q&A Reference Guide

### Q1: Exactly what data leaves the local environment, and what stays behind?
> Raw logs, usernames, real IP addresses and secrets stay local. Approved metadata includes typed measurements, UTC timestamps, HMAC pseudonyms, collector health and aggregated threat summaries.

### Q2: How do you prove that secrets were not sent?
> The local proof panel at `http://localhost:9001/audit` shows the exact outbound JSON for inspection. Matching its SHA-256 digest with the SaaS receipt confirms that the inspected bytes match the received bytes.

### Q3: What happens when SaaS is unreachable?
> The collector commits approved events to a disk-backed outbox before sending. Retries use exponential backoff and stable payload IDs. In the tested outage, every queued ID and digest matched the committed SaaS evidence after replay.

### Q4: How does your AIOps distinguish real anomalies from normal spikes?
> The rolling detector warms up on ten samples and needs two consecutive positive z-scores above 3. Fixed severe thresholds can trigger immediately.

### Q5: What safeguards exist before automated remediation executes?
> Heimdal enforces human-in-the-loop authorization. Actions require operator role authentication, can only target pre-approved demo targets, are rate-limited to 3 per hour, capture an atomic state snapshot before modification, and support single-click rollback.
