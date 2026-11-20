<p align="center">
  <img src="assets/banner.png" alt="Heimdal Observability Platform" width="650" />
</p>

# Heimdal: Privacy-Preserving Observability and AIOps Platform

Built for the CICADA 2026 hackathon.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![React: 19](https://img.shields.io/badge/react-19-cyan.svg)](https://react.dev/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green.svg)](https://fastapi.tiangolo.com/)
[![SQLite: WAL](https://img.shields.io/badge/SQLite-WAL%20%7C%20FULL-lightgrey.svg)](https://sqlite.org/)

Heimdal is an AIOps observability platform designed to monitor distributed services without sending raw logs, credentials, or sensitive customer records across network boundaries.

> Quick links: [Run the live demo](docs/RUNBOOK.md) · [Member 1 Lead](.planning/MEMBER_1_LEAD.md) · [Member 2 Dashboard](.planning/MEMBER_2_DASHBOARD.md) · [Member 3 Validation](.planning/MEMBER_3_VALIDATION.md) · [Contracts](.planning/CONTRACTS.md) · [Architecture](.planning/ARCHITECTURE.md)

The system separates collection and central analysis into two tiers:
1. Customer-local collector: Runs inside the customer environment. It filters, redacts, and aggregates telemetry locally. Raw logs, secrets, and customer data never leave this boundary. An SQLite outbox buffers records during outages, and a local loopback server displays the outbound payload and cryptographic digest.
2. Central SaaS platform: An authenticated, multi-tenant analytics service. It ingests allow-listed metadata only, tracks fleet health across four states (Excellent, Good, Fair, Poor), detects statistical anomalies with heuristic evidence scoring, correlates related alerts into incidents, and supports operator-approved remediation.

---

## Table of Contents

- [Trust Boundary](#trust-boundary)
- [Key Features](#key-features)
- [System Architecture](#system-architecture)
- [Performance Targets](#performance-targets)
- [8 Live Hackathon Scenarios](#8-live-hackathon-scenarios)
- [Technology Stack](#technology-stack)
- [Repository Structure](#repository-structure)
- [Getting Started & Local Setup](#getting-started--local-setup)
- [Documentation Index](#documentation-index)
- [Team Roles](#team-roles)
- [Status and Limitations](#status-and-limitations)

---

## Trust Boundary

The system enforces a clear boundary between local collection and central storage:

| Boundary Domain | Tier 1: Customer Local Collector | Tier 2: Central SaaS Platform |
|---|---|---|
| Raw Logs and Payloads | A bounded local preview keeps up to 500 records for 15 minutes. | Raw fields are excluded from approved payloads. |
| Passwords and API Keys | Known formats are masked in the local preview. | The metadata schema rejects unapproved fields. |
| Source Identifiers | Source names are pseudonymized using a tenant HMAC key. | Receives opaque source IDs. |
| Security Events | Evaluates auth failures locally; produces aggregated threat summaries. | Receives failure counts, risk scores, and pseudonymous attacker IDs. |
| Egress Inspection | Serves an inspection panel over loopback HTTP (`127.0.0.1:9001`). | Receives SHA-256 wire digest matching local outbound bytes. |
| Network Security | Verified HTTPS with CA and hostname checks to the assigned ingest route. | Multi-tenant storage scoped by tenant ID. |

## System Architecture

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
│                            │                        │ │ (React 19 + Vite)         │ │
│                            │                        │ └───────────────────────────┘ │
└────────────────────────────┘                        └───────────────────────────────┘
```

---

## Key Features

### 1. Privacy-Preserving Metadata Pipeline & Egress Proof Panel
* Pydantic v2 models forbid extra keys (`extra="forbid"`). Allowed numeric fields include `cpu_pct`, `memory_pct`, `disk_used_pct`, `disk_read_bps`, `disk_write_bps`, `net_tx_bps`, `net_rx_bps`, `latency_ms`, `packet_loss_pct`, `service_available`, and `connectivity`.
* A local regex catalog filters API tokens, JWTs, AWS keys, Bearer tokens, and connection strings prior to serialization.
* Operators can open a local loopback window (`http://localhost:9001/audit`) to review raw input alongside exact outbound JSON wire bytes.
* The collector saves canonical serialized bytes and computes their SHA-256 digest. The SaaS ingest endpoint computes the digest upon receipt and returns an `IngestReceipt`. Both digests must match bit for bit.

### 2. Resilient Offline Buffering & Transactional Deduplication
* Events commit to an SQLite outbox database before network transmission begins.
* The database uses `PRAGMA synchronous = FULL` and WAL mode to prevent corruption across sudden restarts.
* Exponential backoff with jitter (`1s`, `2s`, `4s`, `8s`) governs retries during SaaS outages. Collector heartbeats run on an independent loop and do not block behind telemetry backlogs.
* Every payload carries a deterministic `payload_uuid` (UUIDv5). The SaaS database enforces a `UNIQUE(tenant_id, payload_uuid)` constraint; replayed records return the original receipt without double-counting metrics or re-triggering incidents.

### 3. Four-State Operational Health Engine
Monitored sources and collectors are evaluated into one of four states:
* Excellent: All metrics report within expected baseline boundaries.
* Good: Minor metric drift without operational failure.
* Fair: Elevated latency, packet loss, or warning thresholds reached.
* Poor: Collector offline (55-second heartbeat expiry with a one-second watchdog), severe resource exhaustion, or security breach.
* Late or replayed events do not modify current live health. State transitions are timestamped in UTC and stored with machine-readable reason codes.

### 4. Explainable AIOps Anomaly Detection & Incident Correlation
* Rolling mean and standard deviation z-score detector ($z = \frac{x - \mu}{\sigma}$) with an adaptive variance floor ($\sigma_{\text{floor}}$) to avoid false positives during low-variance periods.
* Incidents display observed values, historical baselines, contributing metric IDs, and a heuristic evidence score (0 to 100). Calibrated confidence and root-cause certainty are deliberately omitted per policy.
* The incident engine groups related alerts across configured topology dependencies within a sliding time window while keeping unrelated tenant alerts separate.

### 5. Policy-Guarded Autonomous Ops Simulation
* Remediation actions operate on pre-approved simulated targets (`SCALE_CONTAINER_MEMORY`).
* State lifecycle progresses from `proposed` to `approved` (requires operator role), `executing`, and `succeeded`.
* The collector persists the snapshot and simulated capacity change in SQLite. After the action succeeds, an operator can restore the original limit.

---

## Performance Targets

Measured against the evaluation test suite:

| Metric | Target | Measurement Method | Verification Check |
|---|---|---|---|
| Collection-to-Dashboard Latency | $\le 10\text{s}$ at $p95$ | Telemetry event timestamp vs. React first-visible-render timestamp | `V10` |
| Threshold Breach to Alert Raised | $\le 15\text{s}$ | Injected fault timestamp vs. alert creation in SaaS database | `V07`, `V10` |
| Collector Offline Detection | $\le 60\text{s}$ | Last heartbeat timestamp vs. status transition to `Poor` | `V05`, `V10` |
| Post-Outage Backlog Delivery | $100\%$ delivery (0 loss, 0 dupes) | Sent UUID set vs. received UUID set after 30s network cutoff | `V04` |

---

## 8 Live Hackathon Scenarios

The test harness exercises all 8 evaluation scenarios:

| # | Scenario Title | Injected Condition | Expected System Behavior | Check ID |
|---|---|---|---|---|
| 1 | Raw Log Contains a Secret | Ingest log lines with embedded AWS keys, JWTs, and passwords. | Raw secrets remain local; sanitized metadata reaches SaaS; egress proof shows exact redaction. | `V03` |
| 2 | Collector Loses Connectivity | Simulate 30s SaaS network outage. | Collector buffers records in SQLite outbox; drains upon reconnect; 0 records lost, 0 duplicates. | `V04` |
| 3 | Repeated Failed Logins | Ingest $\ge 5$ failed login attempts within 10s. | Local security analyzer triggers; exports typed threat summary; 0 raw usernames/passwords egress. | `V06` |
| 4 | Network Latency Rises | Inject packet latency spike and loss on primary source. | Latency alert raised $\le 15\text{s}$; downstream dependency impact reflected on dashboard. | `V07` |
| 5 | Resource Anomaly (CPU/Memory) | Inject sudden deviation against warm baseline. | Rolling z-score flags anomaly; cites baseline $\mu$, $\sigma$, and heuristic score. | `V08` |
| 6 | Alert Storm Correlation | Multi-signal storm across connected dependency graph. | Alerts grouped into single incident; concurrent unrelated tenant alerts remain strictly isolated. | `V08` |
| 7 | Duplicate & Out-of-Order Delivery | Transmit duplicate UUIDs and late historical timestamps. | Deduplication ignores duplicate analytic effects; late events placed by event time without altering live health. | `V09` |
| 8 | Remediation & Rollback | Memory leak incident triggers scaling recommendation. | Operator reviews proposal, approves action; collector executes scale; operator triggers snapshot rollback. | `V11` |

---

## Technology Stack

```
               HEIMDAL TECHNOLOGY STACK
┌────────────────────────────────────────────────────────┐
│                        FRONTEND                        │
│  React 19  │  TypeScript  │  Vite  │  Plain CSS / SVG  │
│  2-Second Polling  │  Browser First-Render Profiling   │
└───────────────────────────┬────────────────────────────┘
                            │ Verified HTTPS (JSON)
┌───────────────────────────┴────────────────────────────┐
│                      CENTRAL SAAS                      │
│  Python 3.11+  │  FastAPI  │  Uvicorn  │  HTTPX        │
│  Pydantic v2 (Strict)  │  SQLite (aiosqlite WAL/FULL)  │
│  Multi-Tenant RBAC  │  Rolling Z-Score Anomaly Engine  │
└───────────────────────────┬────────────────────────────┘
                            │ Verified HTTPS + scoped token
┌───────────────────────────┴────────────────────────────┐
│                    LOCAL COLLECTOR                     │
│  Python 3.11+ Daemon  │  Local Regex Scrubbing Engine  │
│  SQLite Outbox Buffer  │  Loopback Egress Proof (HTTP) │
│  Deterministic UUIDv5  │  Autonomous Simulation Worker │
│  Four-State Health    │  AI-SPEC Contracts Enforced   │
└────────────────────────────────────────────────────────┘
```

---

## Repository Structure

```
monitor/
├── .planning/                  # Authoritative planning and specifications
│   ├── ARCHITECTURE.md         # Trust boundary and network specification
│   ├── CONTRACTS.md            # Complete API schemas and data contracts
│   ├── REQUIREMENTS.md         # 43 canonical project requirements
│   ├── ROADMAP.md              # 8-phase milestone breakdown and acceptance gates
│   ├── STATE.md                # Project status, gate progress, and evidence log
│   ├── TEAM_EXECUTION.md       # Ownership matrix across M1, M2, and M3
│   ├── VALIDATION.md           # 14 acceptance checks (V00 to V13) and test catalog
│   └── phases/                 # Individual capability phase plans (01 to 08)
├── docs/                       # Project documentation
│   ├── ARCHITECTURE.md         # Architecture and trust boundary guide
│   ├── API.md                  # REST API reference (SaaS and Local Collector)
│   ├── RUNBOOK.md              # Live demonstration and judge evaluation guide
│   └── CONTRIBUTING.md         # Development guide, code standards, and PR workflow
├── backend/                    # Python 3.11+ backend services
│   ├── shared/                 # Shared Pydantic models, schemas, and cryptographic helpers
│   ├── collector/              # Tier 1 Local Collector daemon and outbox pipeline
│   │   ├── adapters/           # Input adapters (JSONL and synthetic generator)
│   │   ├── static/             # Local Egress Proof Panel HTML
│   │   └── demo_source.py      # Controllable simulation source for demo scenarios
│   └── saas/                   # Tier 2 Central SaaS service
│       ├── auth.py             # Tenant and role credential verification
│       ├── storage.py          # SQLite database layer with idempotent transactions
│       ├── health.py           # 4-state health engine and watchdog
│       ├── benchmark.py        # Browser render and offline delay benchmark engine
│       └── main.py             # FastAPI entry point
├── frontend/                   # Operations Dashboard (React 19 + TypeScript + Vite)
│   ├── src/
│   │   ├── components/         # Fleet, Incidents, Egress Inspector, Remediation UI
│   │   ├── api/                # Typed SaaS API client with 2s polling
│   │   └── App.tsx
│   └── package.json
├── tests/                      # Automated test suite
│   ├── core/                   # Unit and integration tests for contracts, security, and outbox
│   ├── scenarios/              # Black-box verifiers for all 8 hackathon scenarios
│   └── ui/                     # Frontend integration and latency timing tests
└── scripts/                    # Operational and validation scripts
    ├── security/               # Local dev CA and server SAN certificate generation
    └── verification/           # Runner scripts for evaluation suite
```

---

## Getting Started & Deployment

Choose the setup that fits your target environment:

### Method A: One-Command Deployment with Docker (Recommended)
No Python, Node.js, or virtual environments required on the host system.

```bash
# Clone and enter the repository
git clone https://github.com/shouryasingh2311/HeimDall.git
cd HeimDall

# Build and start all services
docker compose up
```

Once running:
* **Operations Dashboard**: `https://localhost:8443` (served over HTTPS with React UI)
* **Scenario Verification**: `http://localhost:9001/scenarios` (isolated chaos engine)
* **Local Egress Proof**: `http://localhost:9001/audit` (zero-raw-log loopback proof)
* **Operator Token**: Printed directly in the startup banner for easy copy-paste.

---

### Method B: One-Command Native Quick Start (No Docker)
If Docker is not available on the target system, automated startup scripts handle virtual environment creation, dependencies, frontend compilation, and TLS bootstrap automatically:

**On Windows (PowerShell):**
```powershell
git clone https://github.com/shouryasingh2311/HeimDall.git
cd HeimDall
.\start.ps1
```

**On Linux / macOS (Bash):**
```bash
git clone https://github.com/shouryasingh2311/HeimDall.git
cd HeimDall
chmod +x start.sh
./start.sh
```

---

### Method C: Manual Development Setup

#### Prerequisites
* Python: 3.11 or newer.
* Node.js: v22.12.0 or newer with `npm`.
* Operating System: Windows, macOS, or Linux.

#### 1. Environment Setup
```bash
# Clone the repository
git clone https://github.com/shouryasingh2311/HeimDall.git
cd HeimDall

# Backend setup (Python virtual environment)
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -e .

# Frontend setup
npm --prefix frontend ci
npm --prefix frontend run build
```

#### 2. Bootstrap Local Certificates & Credentials
Heimdal enforces TLS and cryptographic tokens. Run the security bootstrap tool to generate the local development CA, localhost SAN certificates, and tenant credentials in `.heimdal/dev/`:
```bash
python -m scripts.security.bootstrap
```
This provisions:
* CA root (`.heimdal/dev/ca.pem`), server certificate (`server.pem`) and private key (`server.key`).
* Tenant Alpha credentials: `.heimdal/dev/collector-alpha.json` and `.heimdal/dev/operator-alpha.json`.
* Tenant Beta credentials: `.heimdal/dev/collector-beta.json` and `.heimdal/dev/operator-beta.json`.

To export OpenAPI schemas and synthetic fixtures for frontend development:
```bash
python -m scripts.security.export_contracts
```

#### 3. Running Central SaaS Service
Start the central SaaS platform over HTTPS:
```bash
python -m backend.saas.main --dashboard frontend/dist
```
* SaaS API & Dashboard: `https://localhost:8443`
* Public health check: `https://localhost:8443/healthz`
* Query fleet status with generated operator credentials:
  ```powershell
  $operator = Get-Content -Raw .heimdal/dev/operator-alpha.json | ConvertFrom-Json
  curl.exe --cacert .heimdal/dev/ca.pem -H "Authorization: Bearer $($operator.token)" -H "X-Tenant-ID: $($operator.tenant_id)" https://localhost:8443/api/v1/fleet
  ```

#### 4. Running the Local Collector
In a separate terminal, start the local collector daemon:
```bash
python -m backend.collector.daemon --scenarios
```
* To run for Tenant Beta: `python -m backend.collector.daemon --tenant beta`
* To run a single batch and exit: `python -m backend.collector.daemon --once`
* To ingest local JSONL logs: `python -m backend.collector.daemon --input path/to/events.jsonl`
* Local Egress Proof Panel: Open `http://localhost:9001/audit` in your browser. Enter the `local_token` from `.heimdal/dev/collector-alpha.json` to inspect the raw input preview, sanitized outbound bytes, and matching SaaS receipt.

#### 5. Opening the Operations Dashboard
Open <https://localhost:8443> and enter the tenant ID and operator token from `.heimdal/dev/operator-alpha.json`. The [judge runbook](docs/RUNBOOK.md) covers browser CA trust, the scenario runner, and the full demo.

#### 6. Running Validation Suite
```bash
# Run core security, schema, and deduplication tests
python -m pytest tests/core

# Run the scenario fixtures and adapter checks
python -m pytest tests/scenarios

# Run UI verification checks
node tests/ui/test-client.mjs
```

For the full regression with Edge and all eight scenarios, follow the [verification commands](docs/RUNBOOK.md#4-run-the-automated-checks-for-phases-18).

---

## Documentation Index

* [Architecture & Trust Boundaries](docs/ARCHITECTURE.md): Network flow, encryption protocols, and transactional outbox mechanics.
* [Phase 1 Runbook](docs/PHASE1.md): Procedures for running and validating the Phase 1 core architecture and transport.
* [REST API Reference](docs/API.md): Endpoint catalog for both SaaS and Local Collector services.
* [Judge Evaluation Runbook](docs/RUNBOOK.md): Step-by-step walkthrough for verifying each of the 8 hackathon scenarios.
* [Developer & Contributing Guide](docs/CONTRIBUTING.md): Team git workflow, code ownership boundaries, and testing rules.
* [Interface Authority (CONTRACTS.md)](.planning/CONTRACTS.md): Nested schemas, field limits, and wire-receipt hashing specs.
* [Acceptance Catalog (VALIDATION.md)](.planning/VALIDATION.md): Specifications for checks `V00` through `V13`.

---

## Team Roles

The project is structured for a 3-member parallel development workflow:

| Role | Member | Focus Areas & Owned Files |
|---|---|---|
| M1: Lead / Core | Project Lead | Architecture, shared Pydantic models (`backend/shared/**`), security sanitizer, outbox persistence, SaaS API (`backend/saas/**`), AIOps detector, and integration. |
| M2: Operations Dashboard | Frontend Teammate | React 19 / Vite client (`frontend/**`), fleet health widgets, egress receipt inspector, incident views, and render-to-frame latency timing. |
| M3: Validation & Adapters | Validation Teammate | Telemetry adapters (`backend/collector/adapters/**`), demo source, local HTML proof UI, 8 scenario harnesses (`tests/scenarios/**`), and runbook. |

---

## Status and Limitations

### Current Status
* All 8 Phases are fully integrated on `main`. The [Phase 8 evidence record](.planning/phases/08-unified-operations-dashboard-judge-verification-suite/08-01-SUMMARY.md) describes the synthetic demo rehearsal.
* Gates G0 through G6 achieved.
* Runtime includes HTTPS SaaS, loopback Collector daemon, local HTML proof inspector, scenario verification engine, and React 19 / Vite dashboard.
* Checks V01 through V12 verified with synthetic and live test evidence.
* V00 remains blocked until the official organizer telemetry stream is verified.

### Scoped Boundaries
* Single-process SQLite: Uses SQLite WAL/FULL for local durability without multi-container operational overhead.
* Simulated Remediation: Autonomous operations are bounded to the `SCALE_CONTAINER_MEMORY` simulation playbook.
* Regional Data Residency: Enforced via token-to-endpoint routing; multi-region physical infrastructure is documented rather than provisioned.
