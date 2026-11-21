# 🛡️ HeimDall: Technical Demonstration & Linux Pitch Playbook

> **High-Impact Presentation & Technical Demonstration Guide**  
> *Production-Grade Privacy-First Distributed Observability and AIOps Platform.*

---

## ⚡ The 30-Second Elevator Pitch

> *"Traditional enterprise monitoring forces an unacceptable compromise: to get centralized visibility and AIOps, companies must ship raw logs, customer payloads, and sensitive credentials outside their firewalls.*  
>  
> *We built **HeimDall**: a privacy-first, two-tier AIOps platform. Our core thesis is: **Sensitive data never leaves the customer environment, but intelligent operations don't need raw logs to work.**  
>  
> *Our customer-local collector scrubs secrets and emits only allow-listed, HMAC-pseudonymized metadata over verified TLS. Our central SaaS correlates microservice incidents, explains root causes with statistical z-scores, and executes policy-bounded autonomous remediation with instant snapshot rollback."*

---

## 🐧 Linux / WSL Installation & Startup Methods

HeimDall is 100% cross-platform and natively optimized for **Linux VMs (Ubuntu/Debian)** and **WSL2**. Choose any of the following 4 methods:

### Method 1: The Remote Zero-Git One-Liner (Fastest for Judges)
Installs dependencies, builds frontend, bootstraps TLS CA, and boots both tiers with zero manual steps:
```bash
curl -fsSL https://raw.githubusercontent.com/shouryasingh2311/HeimDall/main/install.sh | bash
```

---

### Method 2: Docker Compose (1-Command Containerized Deployment)
Runs both SaaS and Collector inside an isolated, containerized Linux environment:
```bash
# Clone and enter repo (or run from current folder)
git clone https://github.com/shouryasingh2311/HeimDall.git
cd HeimDall

# Build and start services
docker compose up --build
```
*Maps ports `8443` (SaaS HTTPS) and `9001` (Collector Local Audit).*

---

### Method 3: Native Linux Launcher Script
Automatically configures a Python virtual environment, compiles the React 19 UI, and launches background daemons:
```bash
cd HeimDall
chmod +x start.sh
./start.sh
```

---

### Method 4: Manual Multi-Terminal Execution (For Maximum Transparency)
If you want to observe raw logs in real time across separate terminal windows:

#### Terminal 1: Central SaaS Platform
```bash
# 1. Setup virtual environment & dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# 2. Bootstrap TLS certificates & tenant credentials
python -m scripts.security.bootstrap --runtime .heimdal/demo

# 3. Start Central SaaS server (FastAPI + TLS + React UI)
python -m backend.saas.main --runtime .heimdal/demo --dashboard frontend/dist
```

#### Terminal 2: Customer Collector Daemon
```bash
source .venv/bin/activate

# Start local collector daemon with scenario engine enabled
python -m backend.collector.daemon --runtime .heimdal/demo --scenarios
```

---

## 🌐 Active Live Endpoints & Port Map

| Component | Network Endpoint | Purpose & Access |
| :--- | :--- | :--- |
| **Central SaaS Dashboard** | `https://localhost:8443` | Unified Operations UI (Fleet, Incidents, Benchmarks). |
| **Local Egress Proof Inspector** | `http://localhost:9001/audit` | Customer-local side-by-side privacy proof. |
| **Interactive Scenario Runner** | `http://localhost:9001/scenarios` | 8-Scenario live chaos trigger panel. |

> 💡 **WSL2 Localhost Forwarding:** Even when running inside WSL2, you can open your normal Windows browser (Chrome, Edge) directly at `https://localhost:8443`.

---

## 🎯 The 5-Minute Step-by-Step Live Demo Script

### Minute 1: Fleet & Real-Time Performance Benchmarks
1. Open **`https://localhost:8443`** in your browser.
2. In the top connection bar, enter:
   * **Tenant ID:** `tenant-alpha`
   * **Operator Token:** Copy token from `.heimdal/demo/operator-alpha.json` (or terminal startup banner)
   * Click **Connect dashboard**.
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

1. Open a second tab to `http://localhost:9001/scenarios` (use `local_token` from `collector-alpha.json`).
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
   * Open **Operator Settings**, change Tenant ID to `tenant-beta`, and click Connect.
   * The fleet and incidents for Tenant Alpha instantly disappear (returns 404). Switch back to `tenant-alpha` to restore visibility.

---

## 🔍 Live Linux Verification Commands (Terminal Probing)

Run these bash commands in a third terminal to prove live execution without dummy scripts:

```bash
# 1. Verify active listening ports in Linux kernel:
ss -tulpn | grep -E '8443|9001'

# 2. Live HTTPS TLS Handshake against SaaS:
curl --cacert .heimdal/demo/ca.pem https://localhost:8443/healthz
# Returns: {"status":"ok"}

# 3. Query authenticated SaaS Fleet API:
OP_TOKEN=$(jq -r '.token' .heimdal/demo/operator-alpha.json 2>/dev/null || grep -o '"token": *"[^"]*"' .heimdal/demo/operator-alpha.json | cut -d'"' -f4)

curl --cacert .heimdal/demo/ca.pem \
  -H "Authorization: Bearer $OP_TOKEN" \
  -H "X-Tenant-ID: tenant-alpha" \
  https://localhost:8443/api/v1/fleet

# 4. Query live local collector audit records:
LOCAL_TOKEN=$(grep -o '"local_token": *"[^"]*"' .heimdal/demo/collector-alpha.json | cut -d'"' -f4)

curl -H "Authorization: Bearer $LOCAL_TOKEN" http://localhost:9001/api/local/audit

# 5. Run live scenario verification CLI against running instance:
python scripts/verification/run_scenarios.py --runtime .heimdal/demo
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
| **Q6: How does the system handle diverse deployment environments (Edge, IoT, Cloud)?** | *"HeimDall separates lightweight data collection from central SaaS analytics. Edge nodes run the single-file local daemon with an embedded SQLite WAL buffer, needing only Python or a tiny Docker container, while the central SaaS scales horizontally to process allow-listed metadata."* |
