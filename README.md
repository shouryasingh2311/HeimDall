# Cicada — Privacy-First Observability & AIOps Platform

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![React: 18](https://img.shields.io/badge/react-18-cyan.svg)](https://react.dev/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green.svg)](https://fastapi.tiangolo.com/)
[![SQLite: WAL](https://img.shields.io/badge/SQLite-WAL%20%7C%20FULL-lightgrey.svg)](https://sqlite.org/)

**Cicada** is an end-to-end, privacy-first AIOps observability platform built for enterprise, cloud, data center, and distributed architectures. Designed according to the [Cicada 2026 Hackathon Specification](file:///c:/Users/Safa%20Asmi/Documents/GitHub/monitor/evaluation_guide_extracted.txt), it solves the core observability dilemma: **delivering centralized operational intelligence without transmitting raw logs, credentials, or sensitive customer records across network boundaries.**

> **Quick Links:** [Run Phase 1 locally](docs/PHASE1.md) · [Member 1 Lead](.planning/MEMBER_1_LEAD.md) · [Member 2 Dashboard](.planning/MEMBER_2_DASHBOARD.md) · [Member 3 Validation](.planning/MEMBER_3_VALIDATION.md) · [Contracts](.planning/CONTRACTS.md) · [Architecture](.planning/ARCHITECTURE.md)

Cicada deploys a strict **Two-Tier Architecture**:
1. **Tier 1 — Customer-Local Collector:** Runs inside the customer environment. It filters, redacts, sanitizes, and aggregates telemetry locally. Raw logs, secrets, and customer data never leave this boundary. It maintains a durable, crash-resilient local outbox (SQLite WAL/FULL) and surfaces an Egress Proof Panel via loopback HTTP.
2. **Tier 2 — Central SaaS Platform:** An authenticated, multi-tenant central analytics service. It ingests allow-listed metadata only, tracks fleet health (Four States: *Excellent, Good, Fair, Poor*), detects statistical anomalies with transparent evidence scoring, correlates related alerts into unified incidents, and supports policy-governed operator remediation.

---

## Table of Contents

- [Core Principles & Trust Boundary](#core-principles--trust-boundary)
- [Key Features](#key-features)
- [System Architecture](#system-architecture)
- [Performance & Reliability Targets](#performance--reliability-targets)
- [8 Live Hackathon Scenarios](#8-live-hackathon-scenarios)
- [Technology Stack](#technology-stack)
- [Repository Structure](#repository-structure)
- [Getting Started & Local Setup](#getting-started--local-setup)
- [Documentation Index](#documentation-index)
- [Team Roles & Execution Model](#team-roles--execution-model)
- [Status & Limitations](#status--limitations)

---

## Core Principles & Trust Boundary

Traditional monitoring platforms demand that raw application logs, network traces, and syslog streams be continuously forwarded to a central cloud. This introduces severe attack surfaces, compliance liabilities (GDPR, HIPAA, SOC 2), and high bandwidth overhead.

Cicada enforces a zero-compromise trust boundary:

| Boundary Domain | Tier 1: Customer Local Collector | Tier 2: Central SaaS Platform |
|---|---|---|
| **Raw Logs & Payloads** | Stored locally (bounded ring buffer; default 500 records / 15 mins). | **Zero transmission.** Strictly dropped by local policy. |
| **Passwords & API Keys** | Scrubbed via regex catalog and strict nested schema allow-lists. | Never received; invalid schemas rejected with `422`. |
| **Source Identifiers** | Salted HMAC pseudonymization (`source_id = HMAC(source_name, secret)`). | Sees only opaque pseudonym IDs; cannot reverse mapping. |
| **Security Events** | Evaluates auth failures locally; produces aggregated threat summaries. | Receives failure counts, risk score, and pseudonymous attacker ID only. |
| **Egress Inspection** | Serves an **Egress Proof Panel** over loopback HTTP (`127.0.0.1:9001/9002`). | Receives SHA-256 wire-digest matching local outbound bytes. |
| **Network Security** | Initiates outbound TLS 1.3 to regional ingest endpoint; verified CA/SAN. | Multi-tenant isolated storage; enforces tenant scope on all operations. |

```
[ Customer Local Environment ]                        [ Central SaaS Boundary ]
┌────────────────────────────┐                        ┌───────────────────────────────┐
│ Raw Logs / System Telemetry│                        │                               │
│             │              │                        │                               │
│             ▼              │                        │                               │
│ ┌────────────────────────┐ │                        │                               │
│ │ Local Security Filter  │ │                        │                               │
│ │  - Drop raw text       │ │                        │                               │
│ │  - Regex scrubbing     │ │                        │                               │
│ │  - Nested schema check │ │                        │                               │
│ └───────────┬────────────┘ │                        │                               │
│             │ (Metadata)   │                        │                               │
│             ▼              │   Verified HTTPS POST  │ ┌───────────────────────────┐ │
│ ┌────────────────────────┐ │ ─────────────────────> │ │ Regional Ingest Endpoint  │ │
│ │ Durable Outbox (SQLite)│ │  (Allow-listed JSON)   │ │  - Tenant credential check│ │
│ │  - WAL mode, FULL sync │ │                        │ │  - Strict Pydantic parse  │ │
│ │  - Canonical wire-bytes│ │ <───────────────────── │ │  - Deduplication commit   │ │
│ └───────────┬────────────┘ │   HTTP 200 + Receipt   │ └─────────────┬─────────────┘ │
│             │              │   (SHA-256 digest)     │               │               │
│             ▼              │                        │               ▼               │
│ ┌────────────────────────┐ │                        │ ┌───────────────────────────┐ │
│ │ Egress Proof Panel     │ │                        │ │ Fleet Analytics & AIOps   │ │
│ │ (Loopback 127.0.0.1)   │ │                        │ │  - 4-State Health Engine  │ │
│ └────────────────────────┘ │                        │ │  - Rolling Z-Score Anomaly│ │
│                            │                        │ │  - Incident Correlator    │ │
│                            │                        │ └─────────────┬─────────────┘ │
│                            │                        │               │               │
│                            │                        │               ▼               │
│                            │                        │ ┌───────────────────────────┐ │
│                            │                        │ │ Operations Dashboard      │ │
│                            │                        │ │ (React 18 + Vite)         │ │
│                            │                        │ └───────────────────────────┘ │
└────────────────────────────┘                        └───────────────────────────────┘
```

---

## Key Features

### 1. Privacy-Preserving Metadata Pipeline & Egress Proof Panel
* **Strict Nested Model Allow-Listing:** Implements Pydantic v2 models forbidding extra keys (`extra="forbid"`). Only typed metrics (`cpu_pct`, `memory_pct`, `disk_used_pct`, `disk_read_bps`, `disk_write_bps`, `net_tx_bps`, `net_rx_bps`, `latency_ms`, `packet_loss_pct`, `service_available`, `connectivity`) are permitted.
* **Local Regex Sanitizer:** High-speed regex engine catches API tokens, JWTs, AWS credentials, Bearer tokens, and connection strings before serialization.
* **Loopback Proof Inspector:** Operators can open a local browser window to view side-by-side comparisons of raw unredacted input versus the exact outbound JSON wire bytes.
* **Deterministic SHA-256 Wire Receipts:** The collector records the exact canonical serialized bytes and their SHA-256 digest. The SaaS ingest endpoint calculates the digest upon arrival and returns an `IngestReceipt`. Both sides must match bit-for-bit.

### 2. Resilient Offline Buffering & Transactional Deduplication
* **Persist-Before-Send Outbox:** Every event is committed to a local SQLite outbox database before network transmission begins.
* **Durable Fault Tolerance:** Configured with `PRAGMA synchronous = FULL` and WAL mode to prevent data corruption during sudden power losses or OS crashes.
* **Smart Backoff & Reconnect:** Exponential backoff with jitter (`1s`, `2s`, `4s`, `8s`) during SaaS outages. Heartbeats run on an independent thread and never block behind backlog draining.
* **Idempotent Ingestion:** Every event carries a deterministic `payload_uuid` (UUIDv5 derived from tenant, collector, source, input ID, and kind). The SaaS database enforces a `UNIQUE(tenant_id, payload_uuid)` constraint. Replays return the original receipt without double-counting metrics, alerts, or incident side-effects.

### 3. Four-State Operational Health Engine
Monitored systems and collectors are evaluated every 2 seconds into one of four distinct states:
* 🟢 **Excellent (Healthy):** All metrics reporting normally within historical baselines.
* 🟡 **Good (Normal):** Minor metric drift without operational impact.
* 🟠 **Fair (Needs Attention):** Elevated latency, packet loss, or recurring warnings.
* 🔴 **Poor (Critical):** Collector offline (>60s heartbeat loss), severe resource exhaustion, or security breach.
* **Staleness Handling:** Late or replayed events cannot falsely refresh live health state. Health transitions are timestamped in UTC and stored with machine-readable reason codes.

### 4. Explainable AIOps Anomaly Detection & Incident Correlation
* **Statistical Anomaly Detection:** Rolling mean and standard deviation z-score detector ($z = \frac{x - \mu}{\sigma}$) with a variance floor ($\sigma_{\text{floor}}$) to eliminate false alarms during quiet periods.
* **Transparent Evidence Scoring:** Incidents display observed values, historical baselines, contributing metric IDs, and a deterministic heuristic evidence score (0–100). No black-box AI latency or hallucinations.
* **Graph & Time-Window Correlation:** Merges cascading alerts across configured topology dependencies within a sliding time window (e.g., database high disk I/O triggering backend latency) while keeping unrelated incidents strictly separated.

### 5. Policy-Guarded Autonomous Ops Simulation
* **Human-in-the-Loop Safeguards:** Implements a controlled remediation pathway for simulated demo targets (`SCALE_CONTAINER_MEMORY`).
* **Multi-Step Lifecycle:** `proposed` $\rightarrow$ `approved` (requires explicit operator role) $\rightarrow$ `executing` $\rightarrow$ `succeeded`.
* **Atomic Snapshot Rollback:** Before any capacity modification, the collector captures a local resource snapshot. The operator can trigger a rollback at any time, restoring original limits and capturing audit telemetry.

---

## Performance & Reliability Targets

As specified in the hackathon evaluation guide, performance targets are measured against the organizer's simulated telemetry stream:

| Metric | Target | Measurement Method | Verification Check |
|---|---|---|---|
| **Collection-to-Dashboard Latency** | $\le 10\text{s}$ at $p95$ | Telemetry event timestamp vs. React first-visible-render timestamp | `V10` |
| **Threshold Breach to Alert Raised** | $\le 15\text{s}$ | Injected fault timestamp vs. alert creation in SaaS database | `V07`, `V10` |
| **Collector Offline Detection** | $\le 60\text{s}$ | Last heartbeat timestamp vs. status transition to `Poor` | `V05`, `V10` |
| **Post-Outage Backlog Delivery** | $100\%$ delivery (0 loss, 0 dupes) | Sent UUID set vs. received UUID set after 30s network cutoff | `V04` |

---

## 8 Live Hackathon Scenarios

Cicada includes automated fixtures and verifiers for all 8 hackathon evaluation scenarios:

| # | Scenario Title | Injected Condition | Expected System Behavior | Check ID |
|---|---|---|---|---|
| **1** | **Raw Log Contains a Secret** | Ingest log lines with embedded AWS keys, JWTs, and passwords. | Raw secrets remain local; sanitized metadata reaches SaaS; egress proof shows exact redaction. | `V03` |
| **2** | **Collector Loses Connectivity** | Simulate 30s SaaS network outage. | Collector buffers records in SQLite outbox; drains upon reconnect; 0 records lost, 0 duplicates. | `V04` |
| **3** | **Repeated Failed Logins** | Ingest $\ge 5$ failed login attempts within 10s. | Local security analyzer triggers; exports typed threat summary; 0 raw usernames/passwords egress. | `V06` |
| **4** | **Network Latency Rises** | Inject packet latency spike and loss on primary source. | Latency alert raised $\le 15\text{s}$; downstream dependency impact reflected on dashboard. | `V07` |
| **5** | **Resource Anomaly (CPU/Memory)** | Inject sudden deviation against warm baseline. | Rolling z-score flags anomaly; cites baseline $\mu$, $\sigma$, and heuristic score; suggests investigation. | `V08` |
| **6** | **Alert Storm Correlation** | Multi-signal storm across connected dependency graph. | Alerts grouped into single incident; concurrent unrelated tenant alerts remain strictly isolated. | `V08` |
| **7** | **Duplicate & Out-of-Order Delivery** | Transmit duplicate UUIDs and late historical timestamps. | Deduplication ignores duplicate analytic effects; late events placed by event time without altering live health. | `V09` |
| **8** | **Remediation & Rollback** | Memory leak incident triggers scaling recommendation. | Operator reviews proposal, approves action; collector executes scale; operator triggers snapshot rollback. | `V11` |

---

## Technology Stack

```
               CICADA TECHNOLOGY STACK
┌────────────────────────────────────────────────────────┐
│                        FRONTEND                        │
│  React 18  │  TypeScript  │  Vite  │  Plain CSS / SVG  │
│  2-Second Polling  │  Browser First-Render Profiling   │
└───────────────────────────┬────────────────────────────┘
                            │ Verified HTTPS (JSON)
┌───────────────────────────┴────────────────────────────┐
│                      CENTRAL SAAS                      │
│  Python 3.11+  │  FastAPI  │  Uvicorn  │  HTTPX        │
│  Pydantic v2 (Strict)  │  SQLite (aiosqlite WAL/FULL)  │
│  Multi-Tenant RBAC  │  Rolling Z-Score Anomaly Engine  │
└───────────────────────────┬────────────────────────────┘
                            │ Mutual / Verified TLS
┌───────────────────────────┴────────────────────────────┐
│                    LOCAL COLLECTOR                     │
│  Python 3.11+ Daemon  │  Local Regex Scrubbing Engine  │
│  SQLite Outbox Buffer  │  Loopback Egress Proof (HTTP) │
│  Deterministic UUIDv5  │  Autonomous Simulation Worker │
└────────────────────────────────────────────────────────┘
```

---

## Repository Structure

```
monitor/
├── .planning/                  # Authoritative GSD planning and architectural specifications
│   ├── ARCHITECTURE.md         # Detailed trust boundary and network specification
│   ├── CONTRACTS.md            # Complete API schemas and data contracts
│   ├── REQUIREMENTS.md         # 43 canonical project requirements
│   ├── ROADMAP.md              # 8-phase milestone breakdown and acceptance gates
│   ├── STATE.md                # Project status, gate progress, and evidence log
│   ├── TEAM_EXECUTION.md       # Ownership matrix across M1, M2, and M3
│   ├── VALIDATION.md           # 14 acceptance checks (V00–V13) and test catalog
│   └── phases/                 # Individual capability phase plans (01 to 08)
├── docs/                       # Project documentation
│   ├── ARCHITECTURE.md         # Architecture deep-dive and trust boundary guide
│   ├── API.md                  # Comprehensive REST API reference (SaaS & Local)
│   ├── RUNBOOK.md              # Live demonstration and judge evaluation guide
│   └── CONTRIBUTING.md         # Developer guide, code standards, and PR workflow
├── backend/                    # Python 3.11+ backend services
│   ├── shared/                 # Shared Pydantic models, schemas, and cryptographic helpers
│   ├── collector/              # Tier 1 Local Collector daemon and outbox pipeline
│   │   ├── adapters/           # Input adapters (Organizer JSONL / synthetic generator)
│   │   ├── static/             # Local Egress Proof Panel HTML/JS
│   │   └── demo_source.py      # Controllable simulation source for demo scenarios
│   └── saas/                   # Tier 2 Central SaaS service
│       ├── auth.py             # Tenant and role credential verification
│       ├── storage.py          # SQLite database layer with idempotent transactions
│       ├── aiops.py            # Rolling z-score detector & incident correlator
│       └── main.py             # FastAPI entry point
├── frontend/                   # Operations Dashboard (React 18 + TypeScript + Vite)
│   ├── src/
│   │   ├── components/         # Fleet, Incidents, Egress Inspector, Remediation UI
│   │   ├── api/                # Typed SaaS API client with 2s polling
│   │   └── App.tsx
│   └── package.json
├── tests/                      # Automated test suite
│   ├── core/                   # Unit and integration tests for contracts, security, and outbox
│   ├── scenarios/              # Black-box verifiers for all 8 hackathon scenarios
│   └── ui/                     # Frontend integration and latency timing tests
├── scripts/                    # Operational and validation scripts
│   ├── security/               # Local dev CA and server SAN certificate generation
│   └── verification/           # Runner scripts for judge validation suite
├── AGENTS.md                   # Multi-agent collaboration agreement
├── GEMINI.md                   # Gemini teammate specific guidance
├── PROJECT_OVERVIEW.md         # High-level overview and kickoff notes
└── README.md                   # This front-door document
```

---

## Getting Started & Local Setup

### Prerequisites
* **Python:** 3.11 or newer (Python 3.15 supported).
* **Node.js:** v18.0.0 or newer (v22+ recommended) with `npm`.
* **Operating System:** Windows, macOS, or Linux.

### 1. Environment Setup

```bash
# Clone the repository
git clone https://github.com/your-org/monitor.git
cd monitor

# Backend setup (Python virtual environment)
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# Install backend dependencies
pip install -r requirements.txt

# Frontend setup
cd frontend
npm install
cd ..
```

### 2. Generate Development TLS Certificates
To maintain realistic zero-compromise security, collector-to-SaaS communication requires valid TLS with CA verification:
```bash
python scripts/security/generate_certs.py
```
This generates a local development CA and localhost SAN certificates inside `certs/`.

### 3. Running Central SaaS Service
```bash
uvicorn backend.saas.main:app --host 127.0.0.1 --port 8443 --ssl-keyfile certs/saas.key --ssl-certfile certs/saas.crt
```
* SaaS API runs at: `https://127.0.0.1:8443`
* Health probe: `https://127.0.0.1:8443/healthz`

### 4. Running the Local Collector
In a separate terminal:
```bash
# Start Collector for Tenant Alpha
python -m backend.collector.daemon --tenant tenant-alpha --port 9001
```
* Loopback Egress Proof Panel: `http://127.0.0.1:9001/`
* Local Status API: `http://127.0.0.1:9001/api/local/status`

### 5. Running the Operations Dashboard
In a third terminal:
```bash
cd frontend
npm run dev
```
* Dashboard UI: `http://localhost:5173`

### 6. Running Validation Suite
```bash
# Run core security, schema, and deduplication tests
python -m pytest tests/core

# Run all 8 hackathon scenario verifiers
python -m pytest tests/scenarios
```

---

## Documentation Index

Comprehensive documentation is organized across dedicated guides:

* 📘 [Architecture & Trust Boundaries](file:///c:/Users/Safa%20Asmi/Documents/GitHub/monitor/docs/ARCHITECTURE.md) — Exhaustive network flow, encryption protocols, and transactional outbox mechanics.
* 📕 [REST API Reference](file:///c:/Users/Safa%20Asmi/Documents/GitHub/monitor/docs/API.md) — Complete endpoint catalog for both SaaS and Local Collector services.
* 📗 [Judge Evaluation Runbook](file:///c:/Users/Safa%20Asmi/Documents/GitHub/monitor/docs/RUNBOOK.md) — Step-by-step walkthrough for verifying each of the 8 hackathon scenarios.
* 📙 [Developer & Contributing Guide](file:///c:/Users/Safa%20Asmi/Documents/GitHub/monitor/docs/CONTRIBUTING.md) — Team git workflow, code ownership boundaries, and testing rules.
* 📋 [Interface Authority (CONTRACTS.md)](file:///c:/Users/Safa%20Asmi/Documents/GitHub/monitor/.planning/CONTRACTS.md) — Strict nested schemas, field limits, and wire-receipt hashing specs.
* 🎯 [Acceptance Catalog (VALIDATION.md)](file:///c:/Users/Safa%20Asmi/Documents/GitHub/monitor/.planning/VALIDATION.md) — Detailed specifications for checks `V00` through `V13`.

---

## Team Roles & Execution Model

The project is structured for a 3-member parallel development workflow:

| Role | Member | Focus Areas & Owned Files |
|---|---|---|
| **M1: Lead / Core** | Project Lead | Architecture, shared Pydantic models (`backend/shared/**`), security sanitizer, outbox persistence, SaaS API (`backend/saas/**`), AIOps detector, and integration. |
| **M2: Operations Dashboard** | Frontend Teammate | React 18 / Vite client (`frontend/**`), fleet health widgets, egress receipt inspector, incident views, and render-to-frame latency timing. |
| **M3: Validation & Adapters** | Validation Teammate | Organizer telemetry adapters (`backend/collector/adapters/**`), pure demo source, local HTML proof UI, 8 scenario harnesses (`tests/scenarios/**`), and runbook. |

---

## Status & Limitations

### Current Status
* **Phase:** Planning revision complete.
* **Application Runtime:** Awaiting implementation build.
* **Scenarios Verified:** 0 / 8.

### Scoped Boundaries (Hackathon vs. Production)
* **Single-Process SQLite:** The prototype uses SQLite WAL/FULL for bulletproof local durability without multi-container operational complexity (no Kafka or Redis required for hackathon validation).
* **Simulated Remediation:** Autonomous operations are strictly limited to the `SCALE_CONTAINER_MEMORY` playbook running against an in-memory demo target. Real-world autonomous server mutations are intentionally out of scope.
* **Regional Data Residency:** Regional ingest is enforced via token-to-endpoint routing; geographic physical multi-region cloud deployment is designed and documented rather than physically provisioned.
