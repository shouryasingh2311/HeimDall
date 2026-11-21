# 🛡️ HeimDall: Complete Feature Demonstration Walkthrough

> **Step-by-Step Operator Guide for Presenting and Demonstrating Every Platform Capability.**  
> Follow this exact sequence to showcase the full end-to-end architecture, privacy guarantees, AIOps engine, and autonomous remediation.

---

## 📋 Credentials & Access Quick-Reference

| Interface | URL | Credentials / Tokens |
| :--- | :--- | :--- |
| **Operations Dashboard** | [https://localhost:8443](https://localhost:8443) | **Tenant ID:** `tenant-alpha`<br>**Operator Token:** In `.heimdal/demo/operator-alpha.json` |
| **Local Egress Proof** | [http://localhost:9001/audit](http://localhost:9001/audit) | **Local Token:** In `.heimdal/demo/collector-alpha.json` |
| **Interactive Scenario Runner** | [http://localhost:9001/scenarios](http://localhost:9001/scenarios) | **Local Token:** In `.heimdal/demo/collector-alpha.json` |

---

## 🚀 Pre-Flight Startup (Choose Your OS)

### On Windows
```powershell
.\start.ps1
```
*(Automatically builds the frontend, provisions demo TLS certificates and tokens, launches the SaaS and Collector services, and opens your browser directly to the dashboard.)*

### On Linux / macOS
```bash
chmod +x start.sh
./start.sh
```

---

## 🎯 Step-by-Step Feature Walkthrough

### Feature 1: Fleet Overview & 4-Tier Health State Engine
**Location:** Central Dashboard (`https://localhost:8443`) $\to$ **Fleet & Health State** tab

1. Enter `tenant-alpha` and your Operator Token in the top connection bar, then click **Connect dashboard**.
2. **What to point out:**
   - **5 Distributed Nodes:** `lb-01` (Load Balancer), `api-01` (Gateway), `auth-01` (Security), `db-01` (Database), `worker-01` (Background Processing).
   - **4 Discrete Health States:**
     - 🟢 **Excellent:** Nominal metrics within baseline.
     - 🟡 **Good:** Minor metric jitter without operational risk.
     - 🟠 **Fair:** Elevated latency, packet loss, or warning thresholds reached.
     - 🔴 **Poor:** Node offline, severe exhaustion, or active security breach.
   - **Pure SVG Sparklines:** High-contrast, zero-bloat charts showing live CPU, memory, latency, and packet loss trends.
   - **Node Detail Modal:** Click on any node card (e.g. `api-01`) to open the deep-dive modal showing chronological metric observations.

---

### Feature 2: Real-Time Performance Benchmarks & SLO Gates
**Location:** Fleet View $\to$ Click **"Measured render timing"** banner

1. **What to show:**
   - Evaluates monotonic timestamps directly from the browser's DOM commits (`requestAnimationFrame`) against wire timestamps:
     - **$p95$ Collection-to-Dashboard Latency:** Target $\le 10\text{s}$ (typically $\sim 5\text{–}6\text{s}$).
     - **Breach-to-Alert Latency:** Target $\le 15\text{s}$ (alert raised within seconds of metric deviation).
     - **Offline Watchdog Delay:** Target $\le 60\text{s}$ (offline transition triggered by 55s heartbeat expiry).

---

### Feature 3: Mathematical Proof of Zero-Egress Privacy
**Location:** Local Proof (`http://localhost:9001/audit`) vs Central Dashboard (`https://localhost:8443`) $\to$ **Payload Egress Inspector** tab

> *This proves that customer raw logs and credentials never leave the local environment.*

1. Open `http://localhost:9001/scenarios` in a separate browser tab and enter the `local_token`.
2. Click **Start** on **Scenario 1: Local secret handling**.
3. Copy the returned **Payload UUID**.
4. Open `http://localhost:9001/audit`, paste the UUID, and click **Fetch local evidence**:
   - **Local Input Preview (Left):** Point out that database passwords and AWS keys are scrubbed with `[REDACTED]`.
   - **Approved Outbound Bytes (Right):** Point out that source names are replaced with opaque HMAC pseudonyms (`src-a7f9...`). Raw text strings are completely dropped.
   - Copy the local **SHA-256 Digest**.
5. Switch to Central Dashboard $\to$ **Payload Egress Inspector**:
   - Paste the Payload UUID and click **Inspect Metadata**.
   - Paste the local SHA-256 digest into the verification field.
   - **Outcome:** The green badge verifies **DIGEST MATCH CONFIRMED**.
   - *Key takeaway: Both tiers agree bit-for-bit on the cryptographic hash, proving the inspected wire bytes were never altered and zero secrets egressed.*

---

### Feature 4: Resilient Outbox Buffering & 30-Second Outage Recovery
**Location:** `http://localhost:9001/scenarios` $\to$ **Scenario 2: Outage buffering**

1. Trigger **Scenario 2** in the scenario runner.
2. **What happens under the hood:**
   - Central metadata ingestion is paused for 30 seconds to simulate a network outage.
   - The local collector buffers 75 incoming records into its durable SQLite outbox (`PRAGMA synchronous = FULL`, WAL mode).
   - Heartbeats continue on an isolated transport channel.
3. Once the 30-second cut ends:
   - The collector automatically drains the outbox queue with exponential backoff.
   - Central SaaS confirms 100% receipt with **zero dropped records and zero duplicate counts** via deterministic UUIDv5 deduplication.

---

### Feature 5: Local Authentication Brute-Force Detection
**Location:** `http://localhost:9001/scenarios` $\to$ **Scenario 3: Failed logins**

1. Trigger **Scenario 3** in the scenario runner.
2. **What happens:**
   - The collector observes a rapid burst of failed login attempts.
   - The first 4 failed attempts are held in a 10-second local sliding memory window.
   - On the 5th attempt, the local security analyzer triggers a threat incident.
   - An aggregated threat summary is emitted with an HMAC-pseudonymized origin (`att-01`).
   - **Zero raw usernames or passwords ever cross the wire.**

---

### Feature 6: Explainable AIOps Statistical Anomaly Engine
**Location:** Central Dashboard $\to$ **AIOps Incidents & Remediation** tab

1. Click on an active incident from the left-hand incident queue.
2. Point out the **Signals & Baselines Evidence Table**:
   - Metrics are NOT judged by fragile static thresholds (e.g. `CPU > 80%`).
   - Shows the node's learned **Baseline Mean ($\mu$)** and **Standard Deviation ($\sigma$)** over a 30-sample rolling window.
   - Displays the computed **$z$-Score** ($z = \frac{x - \mu}{\sigma}$). Anomalies require $z > 3.0$ across consecutive samples to eliminate alert fatigue from transient spikes.

---

### Feature 7: Graph Topology Multi-Node Alert Storm Correlation
**Location:** Central Dashboard $\to$ **AIOps Incidents & Remediation** tab

1. In the incident header, point to **Correlated Alert IDs** and **Affected Sources**.
2. **What to explain:**
   - When an upstream service (`lb-01`) degrades, downstream microservices (`api-01`, `db-01`) experience secondary latency.
   - Instead of raising 20 separate alarms, HeimDall traces the configured topology dependency graph.
   - Related alerts within a 60-second temporal window are fused into **one unified incident**, reducing operator noise by over 50%.

---

### Feature 8: Heuristic Evidence Score & Causal Trace
**Location:** Incident Detail $\to$ Top right score card

1. Point to the **Heuristic Evidence Score** (e.g. `88 / 100`).
2. Show the published mathematical formula:
   $$\text{Score} = \min(100, 30 \times \min(\text{metrics}, 2) + 20 \times \text{dependency} + 20 \times \text{temporal\_order})$$
3. Point to **Likely Cause**:
   - Shows causal graph direction: *"An anomaly at lb-01 may have contributed to the signal at dependent source api-01."*
4. Point to **Investigation Notes**:
   - Chronological step-by-step reasoning explaining exactly why the alert was grouped.

---

### Feature 9: Policy-Guarded Remediation & Instant Snapshot Rollback
**Location:** Incident Detail $\to$ Bottom **Simulation Remediation** card

1. Under the incident, view the recommended playbook:
   - **Playbook:** `SCALE_CONTAINER_MEMORY` (Factor: 1.5x)
   - **Policy Verdict:** `demo_policy_allowed`
2. Click **Approve Remediation**:
   - The action transitions from `Proposed` $\to$ `Approved` $\to$ `Executing` $\to$ `Succeeded`.
   - The central audit logs the operator token fingerprint and execution timestamp.
   - The collector executes the scale command in the simulation container.
   - Return to **Fleet View**: observed memory pressure drops immediately below 70%.
3. Click **Rollback to Snapshot**:
   - The system restores the pre-incident container state snapshot captured prior to modification.
   - Memory allocation returns safely to initial limits.

---

### Feature 10: Strict Multi-Tenant Cryptographic Isolation
**Location:** Top bar $\to$ Click **"Scope Settings"** or Tenant ID

1. In the top bar, change the Tenant ID from `tenant-alpha` to `tenant-beta`.
2. Enter the Operator Token for Tenant Beta from `.heimdal/demo/operator-beta.json`.
3. Click **Connect dashboard**:
   - The browser cache and local render state are immediately purged.
   - All Tenant Alpha nodes, incidents, and audit trails disappear from the screen.
   - Reconnecting with `tenant-alpha` credentials restores Alpha's state without cross-tenant bleed.

---

### Backup Feature: Offline Mock Fixtures Mode
**Location:** Top right header $\to$ Click **"Use Mock Fixtures"**

- If demonstrating in an environment with restricted port access or offline networks, toggle **"Use Mock Fixtures"**.
- Instantly hydrates the entire dashboard with fully populated nodes, correlated incident breakdowns, SVG sparklines, and simulated remediation controls.
