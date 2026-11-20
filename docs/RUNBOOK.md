# Judge Evaluation & Live Scenario Runbook

This runbook provides step-by-step instructions for hackathon judges and evaluators to inspect, execute, and verify the **Cicada** observability platform.

---

## 1. Quick Verification Commands

From the project root:

```bash
# 1. Run Core Contracts, Cryptographic & Persistence Tests
python -m pytest tests/core -v

# 2. Run All 8 Hackathon Scenario Verifiers
python -m pytest tests/scenarios -v

# 3. Build Frontend & Verify Bundle Integrity
npm --prefix frontend run build
```

---

## 2. Walkthrough of the 8 Hackathon Scenarios

### Scenario 1: Raw Log Contains a Secret (`V03`)
* **Objective:** Demonstrate that sensitive data (passwords, tokens, API keys) never leave the customer environment.
* **Execution:** Start the collector and SaaS with the synthetic input and live dashboard in [the local runtime guide](PHASE1.md).
* **Judge Verification Steps:**
  1. Open `http://localhost:9001/audit` and enter the collector's local session token.
  2. Fetch a retained record. Check that known credentials are masked in the local preview and that the exact approved outbound body contains only the allowed metadata fields.
  3. Open the live dashboard at `https://localhost:8443` and connect with the operator credentials for the collector's tenant.
  4. Look up the same payload UUID and paste the SHA-256 digest from the local panel. A match confirms the received body matches the inspected outbound body.

---

### Scenario 2: Collector Loses SaaS Connectivity (`V04`)
* **Objective:** Prove zero data loss and resilient buffering during network partitions.
* **Execution:**
  ```bash
  python -m scripts.verification.run_scenario --scenario 2 --outage-seconds 30
  ```
* **Judge Verification Steps:**
  1. The script cuts the HTTPS link between Collector and SaaS for 30 seconds while telemetry continues to generate locally.
  2. Observe the Collector console: exponential backoff triggers (`1s`, `2s`, `4s`, `8s`) and records queue depth in SQLite outbox.
  3. At $T=30\text{s}$, the connection restores.
  4. Observe automatic outbox drain.
  5. The verifier checks:
     $$\text{Unique Sent UUIDs} \equiv \text{Unique Received UUIDs}$$
     $$\text{Lost Records} = 0, \quad \text{Duplicate Analytic Records} = 0$$

---

### Scenario 3: Repeated Failed Logins (`V06`)
* **Objective:** Detect brute-force authentication attacks locally and export threat summaries without leaking credentials.
* **Execution:**
  ```bash
  python -m scripts.verification.run_scenario --scenario 3
  ```
* **Judge Verification Steps:**
  1. Inject 5 failed login attempts within 10 seconds locally.
  2. Inspect the outbound payload on the local proof panel:
     ```json
     {
       "event_type": "auth_threat",
       "security": {
         "failed_attempts_count": 5,
         "window_seconds": 10,
         "risk_score": 85,
         "attacker_id": "hmac_pseudonym_9f8a"
       }
     }
     ```
  3. Confirm that raw usernames, passwords, and source IP addresses are completely absent from the outbound payload.
  4. Confirm that the SaaS dashboard surfaces a Security Warning incident.

---

### Scenario 4: Network Latency Rises (`V07`)
* **Objective:** Detect network degradation and correlate downstream dependency impact.
* **Execution:**
  ```bash
  python -m scripts.verification.run_scenario --scenario 4
  ```
* **Judge Verification Steps:**
  1. The script injects packet loss (15%) and elevated latency (250ms) into `source_id: net-gw-01`.
  2. Observe the dashboard: within $\le 15$ seconds, an alert is raised.
  3. Observe the dependency graph: downstream service `api-service-01` transitions from `Excellent` to `Fair` due to upstream network dependency.

---

### Scenario 5: Resource Anomaly (CPU/Memory) (`V08`)
* **Objective:** Trigger statistical anomaly detection without static threshold limits.
* **Execution:**
  ```bash
  python -m scripts.verification.run_scenario --scenario 5
  ```
* **Judge Verification Steps:**
  1. The collector streams warm baseline metrics ($N=20$, CPU $\sim 20\%$).
  2. A sudden spike to $65\%$ is injected (below traditional $80\%$ static threshold).
  3. The rolling z-score detector computes $z = \frac{65 - 20}{4.2} = 10.7 > 3.0$.
  4. The SaaS dashboard flags an Anomaly Incident, displaying:
     * Observed Value: $65\%$
     * Baseline Mean ($\mu$): $20\%$
     * Standard Deviation ($\sigma$): $4.2\%$
     * Heuristic Evidence Score: $92/100$

---

### Scenario 6: Alert Storm Correlation (`V08`)
* **Objective:** Merge related alerts into a single cohesive incident while preserving tenant and topology isolation.
* **Execution:**
  ```bash
  python -m scripts.verification.run_scenario --scenario 6
  ```
* **Judge Verification Steps:**
  1. Inject simultaneous CPU spike, disk latency increase, and downstream HTTP latency across connected components in Tenant Alpha.
  2. Simultaneously inject an independent network alert in Tenant Beta.
  3. Confirm on the SaaS dashboard:
     * Tenant Alpha displays **1 unified incident** containing 3 correlated signals.
     * Tenant Beta displays an independent, unmerged incident.
     * Alert fatigue is mitigated through topology grouping.

---

### Scenario 7: Duplicate & Out-of-Order Delivery (`V09`)
* **Objective:** Prove idempotent ingestion and accurate event-time trend ordering.
* **Execution:**
  ```bash
  python -m scripts.verification.run_scenario --scenario 7
  ```
* **Judge Verification Steps:**
  1. Inject duplicate payloads with identical `payload_uuid`.
  2. Confirm SaaS database rejects duplicates (`status: duplicate`) without creating duplicate metric entries or re-triggering alerts.
  3. Inject late-arriving packets with timestamp $T - 30\text{min}$.
  4. Confirm that historical charts place the event at $T - 30\text{min}$ in chronological sequence, but current live health is NOT updated by stale data.

---

### Scenario 8: Policy-Guarded Remediation & Snapshot Rollback (`V11`)
* **Objective:** Demonstrate assisted operational remediation with human approval and rollback safeguards.
* **Execution:**
  ```bash
  python -m scripts.verification.run_scenario --scenario 8
  ```
* **Judge Verification Steps:**
  1. A memory exhaustion incident surfaces a proposed remediation: `SCALE_CONTAINER_MEMORY` ($1.5\times$ factor).
  2. Open the SaaS Dashboard incident view. Notice that execution is blocked pending operator authorization.
  3. Click **"Approve Remediation"**.
  4. The SaaS queues the command; the local collector executes it on the demo target after taking an in-memory snapshot (`memory_limit: 512MB` $\rightarrow$ `768MB`).
  5. Fresh telemetry on the dashboard confirms memory pressure drops from $92\%$ to $61\%$.
  6. Click **"Rollback Action"** on the dashboard.
  7. Collector restores snapshot (`512MB`); audit log records the complete lifecycle.

---

## 3. Real-Time Performance Benchmarking Protocol

To measure Cicada against the organizer performance criteria:

```bash
python -m scripts.verification.measure_benchmarks
```

The script calculates:
* **p95 Collection-to-Dashboard Latency:** Evaluates `rendered_at_utc` (captured via `requestAnimationFrame` in React) minus `event_time_utc`. Target: $\le 10\text{s}$.
* **Breach-to-Alert Latency:** Evaluates alert record creation timestamp minus fault injection timestamp. Target: $\le 15\text{s}$.
* **Offline Detection Delay:** Evaluates transition to `Poor` timestamp minus heartbeat termination timestamp. Target: $\le 60\text{s}$.

---

## 4. Judge Q&A Reference Guide

When evaluating teams, judges are encouraged to ask the following key questions:

### Q1: Exactly what data leaves the local environment, and what stays behind?
> **Answer:** Raw log text, original payloads, unredacted syslog lines, passwords, API tokens, usernames, and real IP addresses stay strictly on the local collector host. Only strongly-typed Pydantic metadata leaves: normalized metrics (0–100 floats), UTC event timestamps, HMAC pseudonymous source IDs, health status tokens, and aggregated threat summaries.

### Q2: How do you prove that secrets were not sent?
> **Answer:** The local proof panel at `http://localhost:9001/audit` shows the exact outbound JSON for inspection. Matching its SHA-256 digest with the SaaS receipt confirms that the inspected bytes match the received bytes.

### Q3: What happens when SaaS is unreachable?
> **Answer:** The collector commits every event to an aiosqlite outbox (`PRAGMA synchronous = FULL`, WAL mode) before network send. During an outage, events accumulate safely. The collector uses exponential backoff with jitter (`1s`, `2s`, `4s`, `8s`). Once SaaS is restored, the backlog is drained in order. Deduplication constraints on SaaS ensure zero records are lost and zero duplicates are created.

### Q4: How does your AIOps distinguish real anomalies from normal spikes?
> **Answer:** We use a rolling z-score algorithm with an adaptive variance floor ($\sigma_{\text{floor}}$) over a warm-up baseline ($N \ge 10$). A spike only flags if $|z| \ge 3.0$. Single-point fluctuations are categorized as benign unless sustained across consecutive evaluations.

### Q5: What safeguards exist before automated remediation executes?
> **Answer:** Cicada enforces human-in-the-loop authorization. Actions require operator role authentication, can only target pre-approved demo targets, are rate-limited to 3 per hour, capture an atomic state snapshot before modification, and support single-click rollback.
