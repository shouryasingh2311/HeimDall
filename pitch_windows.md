# 🛡️ HeimDall: Judge Demo & Windows PowerShell Pitch Playbook

> **High-Impact Presentation & Technical Demonstration Guide for Windows**  
> *Targeted for Hackathon Judges evaluating the 24-Hour End-to-End Secure AIOps Observability Challenge.*

---

## ⚡ The 30-Second Elevator Pitch

> *"Traditional enterprise monitoring forces an unacceptable compromise: to get centralized visibility and AIOps, companies must ship raw logs, customer payloads, and sensitive credentials outside their firewalls.*  
>  
> *We built **HeimDall**: a privacy-first, two-tier AIOps platform. Our core thesis is: **Sensitive data never leaves the customer environment, but intelligent operations don't need raw logs to work.**  
>  
> *Our customer-local collector scrubs secrets and emits only allow-listed, HMAC-pseudonymized metadata over verified TLS. Our central SaaS correlates microservice incidents, explains root causes with statistical z-scores, and executes policy-bounded autonomous remediation with instant snapshot rollback."*

---

## 🪟 Windows PowerShell Installation & Startup Methods

HeimDall is 100% native on Windows with zero Unix emulator requirements. Choose any of the following 5 methods:

### Method 1: The Remote Zero-Git One-Liner (Fastest for Judges)
Open PowerShell (Administrator or standard user) and paste:
```powershell
irm https://raw.githubusercontent.com/shouryasingh2311/HeimDall/main/install.ps1 | iex
```
*Downloads the latest release into `~\HeimDall`, creates a Python virtual environment, installs packages, compiles the React frontend, bootstraps TLS certificates, and launches both services automatically.*

---

### Method 2: The 1-Click Batch Launcher (Desktop Double-Click)
1. Open the project folder in Windows File Explorer.
2. Double-click **`run.bat`**.
*Spawns PowerShell, bootstraps the runtime environment, and launches the application.*

---

### Method 3: Native PowerShell Launcher Script
From a PowerShell prompt inside the repository folder:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\start.ps1
```
*Auto-detects Python 3.11+, sets up `.venv`, builds `frontend\dist`, creates demo CA certificates, and starts services.*

---

### Method 4: Docker Desktop on Windows
If Docker Desktop is running on Windows:
```powershell
docker compose up --build
```
*Builds container image, mounts `.heimdal` runtime volume, and binds ports `8443` and `9001`.*

---

### Method 5: Manual Multi-Terminal PowerShell Execution (Maximum Transparency)
If you want to observe raw logs in real time across separate PowerShell terminal windows:

#### Terminal 1: Central SaaS Platform
```powershell
# 1. Setup virtual environment & dependencies
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .

# 2. Bootstrap TLS certificates & tenant credentials
python -m scripts.security.bootstrap --runtime .heimdal\demo

# 3. Optional: Trust the development CA certificate in Edge/Chrome
certutil.exe -user -addstore Root .heimdal\demo\ca.pem

# 4. Start Central SaaS server (FastAPI + TLS + React Dashboard)
python -m backend.saas.main --runtime .heimdal\demo --dashboard frontend\dist
```

#### Terminal 2: Customer Collector Daemon
```powershell
.\.venv\Scripts\Activate.ps1

# Start local collector daemon with scenario engine enabled
python -m backend.collector.daemon --runtime .heimdal\demo --scenarios
```

---

## 🌐 Active Live Endpoints & Port Map

| Component | Network Endpoint | Purpose & Access |
| :--- | :--- | :--- |
| **Central SaaS Dashboard** | `https://localhost:8443` | Unified Operations UI (Fleet, Incidents, Benchmarks). |
| **Local Egress Proof Inspector** | `http://localhost:9001/audit` | Customer-local side-by-side privacy proof. |
| **Interactive Scenario Runner** | `http://localhost:9001/scenarios` | 8-Scenario live chaos trigger panel. |

---

## 🎯 The 5-Minute Step-by-Step Live Demo Script

### Minute 1: Fleet & Real-Time Performance Benchmarks
1. Open **`https://localhost:8443`** in Edge or Chrome.
2. Enter Tenant ID `alpha` and copy the operator token from `.heimdal\demo\operator-alpha.json`, then click **Connect**.
3. **Show the Fleet Overview:**
   * Point out the 5 nodes across the topology (`lb-01`, `api-01`, `db-01`, `worker-01`, `worker-02`).
   * Show the **4 discrete health states**: `Excellent` (Nominal), `Good` (Minor jitter), `Fair` (High load/stale), `Poor` (Expired/outage).
   * Highlight the **pure SVG sparklines**: high-contrast, zero bloated third-party charting libraries.
4. Click **Measured Render Timing**:
   * Show that performance is measured directly from monotonic UTC timestamps:
     * **$p95$ Collection-to-Dashboard Latency:** $\sim 5.7\text{s}$ ($\le 10\text{s}$ mandate met).
     * **Breach-to-Alert Latency:** $\sim 11.2\text{s}$ ($\le 15\text{s}$ mandate met).
     * **Offline Detection Delay:** $\sim 56.5\text{s}$ ($\le 60\text{s}$ mandate met).

---

### Minute 2: Mathematical Proof of Privacy (The "Mic Drop" Moment)
> **Judge Question:** *"Can you prove secrets never left the customer boundary?"*

1. Open a second browser tab to `http://localhost:9001/scenarios` (use `local_token` from `collector-alpha.json`).
2. Click **Start** on **Scenario 1: Local Secret Handling**.
3. Copy the resulting **Payload UUID**.
4. Open `http://localhost:9001/audit`, paste the UUID, and click **Fetch local evidence**:
   * Point out that under **Local input preview**, raw credentials like `password="..."` and `API_KEY` are scrubbed to `[REDACTED]`.
   * Point out that under **Exact approved outbound bytes**, node names are replaced with `src-...` HMAC pseudonyms.
   * Copy the local **SHA-256 Digest**.
5. Switch to SaaS Dashboard $\to$ **Payload Egress Inspector**:
   * Paste the UUID and click **Inspect Metadata**.
   * Paste the local SHA-256 digest into the verification box.
   * **The green badge confirms:** `DIGEST MATCH CONFIRMED`.
   > *"This provides mathematical proof: the exact byte-stream approved locally is identical to what SaaS received, proving zero raw logs or secrets were transmitted."*

---

### Minute 3: Explainable AIOps (Beyond Static Thresholds)
1. Go to **AIOps Incidents & Remediation** and click an active incident.
2. Demonstrate the **Three Pillars of Explainability**:
   * **1. Why Flagged (Causal Analysis):**
     * Show the **Heuristic Evidence Score** ($100/100$) and reasoning:  
       *"Upstream load balancer degradation (`lb-01`) is causing cascading downstream latency in `api-01`; dependency order verified."*
   * **2. Which Signals (Statistical Evidence Table):**
     * Show that HeimDall does not use fragile static thresholds.
     * Point to the **Baseline Mean ($\mu$)**, **Standard Deviation ($\sigma$)**, and computed **$z$-Score** (e.g. $+65.19\sigma$ spike).
     * Mention that single transient spikes are suppressed to eliminate alert fatigue; alerts require 2 consecutive deviations.
   * **3. Why This Action (Remediation Recommendation):**
     * Displays recommended playbook: `SCALE_CONTAINER_MEMORY`.
     * Explains why: *"Memory utilization breached policy limits ($>85\%$); scaling memory by $2\times$ brings pressure back under $70\%$."*

---

### Minute 4: Policy-Guarded Safe Autonomous Ops & Rollback
1. Under the incident remediation box, highlight the enterprise safety badge:  
   **`SAFE SIMULATION PLAYBOOK | simulation: true`**.
2. Explain the policy guardrails:
   * **Human-in-the-Loop:** Actions require authorized operator approval.
   * **Rate-Limiting:** Max 2 remediation actions per hour per source.
3. Click **Approve Remediation**:
   * Status transitions: `Proposed` $\to$ `Approved` $\to$ `Executing` $\to$ `Succeeded`.
   * Switch to Fleet View: show container memory utilization recover below $70\%$.
4. Click **Rollback to Snapshot**:
   * Show that an atomic pre-action state snapshot was captured before execution; clicking rollback safely restores the pre-incident memory capacity.

---

### Minute 5: Outage Resilience & Tenant Data Isolation
1. **Local Outbox Buffering (Scenario 2):**
   * Explain: *"During a 30-second network cut, the collector buffers events into a durable SQLite WAL outbox on disk. Upon reconnect, all 75 queued events flush with zero loss and zero duplicates."*
2. **Strict Tenant Separation:**
   * Open **Operator Settings**, change Tenant ID to `beta`, and click Connect.
   * The fleet and incidents for Tenant Alpha instantly disappear (returns 404). Switch back to `alpha` to restore visibility.

---

## 🔍 Live Windows PowerShell Probing Commands

Open a third PowerShell terminal to prove live execution without dummy scripts:

```powershell
# 1. Verify active listening ports in Windows kernel:
Get-NetTCPConnection -LocalPort 8443, 9001 -State Listen | Select-Object LocalAddress, LocalPort, OwningProcess, State

# 2. Live HTTPS TLS Handshake against SaaS:
curl.exe --cacert .heimdal\demo\ca.pem https://localhost:8443/healthz
# Returns: {"status":"ok"}

# 3. Query authenticated SaaS Fleet API:
$token = (Get-Content .heimdal\demo\operator-alpha.json | ConvertFrom-Json).token

curl.exe --cacert .heimdal\demo\ca.pem `
  -H "Authorization: Bearer $token" `
  -H "X-Tenant-ID: alpha" `
  https://localhost:8443/api/v1/fleet

# 4. Query live local collector audit records:
$localToken = (Get-Content .heimdal\demo\collector-alpha.json | ConvertFrom-Json).local_token

curl.exe -H "Authorization: Bearer $localToken" http://localhost:9001/api/local/audit

# 5. Run live scenario verification CLI against running instance:
python scripts\verification\run_scenarios.py --runtime .heimdal\demo
```

---

## 💡 Judge Q&A Cheat Sheet

| Judge Question | Direct, Confident Answer |
| :--- | :--- |
| **Q1: Exactly what leaves the customer environment and what stays behind?** | *"Raw logs, raw text, usernames, and real IP addresses stay local. Only typed numeric metrics, UTC timestamps, HMAC pseudonyms (`src-...`, `att-...`), collector heartbeats, and aggregated threat summaries leave."* |
| **Q2: How do you prove secrets weren't leaked to SaaS?** | *"Comparing the SHA-256 wire digest on our local audit page (`http://localhost:9001/audit`) with the SaaS receipt proves identical bytes with zero secret leakage."* |
| **Q3: What happens when SaaS is unreachable?** | *"The collector enqueues approved payloads into a local SQLite WAL outbox. Retries use exponential backoff and stable UUIDs. After reconnecting, SaaS de-duplicates via SHA-256 wire digests, guaranteeing zero data loss and zero duplicate counts."* |
| **Q4: How does your AIOps distinguish real anomalies from normal spikes?** | *"We enforce a 10-sample warm-up window, a variance floor to prevent micro-jitter false alarms, and require two consecutive statistical breaches ($z > 3.0$) before raising an alert. Single transient spikes are suppressed."* |
| **Q5: What safeguards exist before automated remediation executes?** | *"We enforce human-in-the-loop authorization, hardcoded `simulation: true`, rate limits of 2 actions per hour per target, an atomic pre-action snapshot, and one-click rollback."* |
| **Q6: What are the current system limitations?** | *"As disclosed in our Runbook, our demo source is synthetic because external organizer stream formats vary; physical multi-region residency and hardware-level container scaling would require production cloud API bindings."* |
