# Heimdal — Demonstration Runbook & Judge Presentation Guide

**Owned by Member 3 (feat/fixtures-validation)**
*Document Version: 1.0 (Prototype Build)*

Start both services with the [live scenario setup](../RUNBOOK.md) before this walkthrough.

---

## 1. Executive Summary & Problem Statement

Heimdal is a privacy-first multi-tenant infrastructure observability platform. In standard enterprise monitoring setups, raw syslog messages, error traces, and system metrics are shipped off-premise to central SaaS backends, frequently exposing unredacted API keys, database credentials, PII, and customer data.

**Heimdal's Core Architecture:**
- **Local Collector Daemon:** Runs inside the customer network boundary. It ingests local telemetry and syslog, executes local security analyzers (e.g. brute-force authentication detection), persists outbound events to a local SQLite WAL outbox, and applies strict allow-list sanitization (`MetadataPayload`).
- **Central Multi-Tenant Platform:** Authenticates collectors via verified TLS credentials, enforces cryptographic tenant isolation, detects statistical anomalies using z-score modeling, correlates alerts by topology, and coordinates policy-guarded remediation commands.

---

## 2. Five-Minute Judge Walkthrough Script

### Act 1: The Local Boundary & Credential Isolation (0:00 – 1:00)
- **Goal:** Prove strict process and network isolation between customer environments and SaaS.
- **Action:** Open two separate browser tabs:
  1. `http://localhost:9001/audit` for the local egress proof.
  2. `https://localhost:8443` for the operator dashboard.
- **Evidence:** Show two tenant configurations (`tenant-alpha` and `tenant-beta`). Highlight that `tenant-alpha` has zero access to `tenant-beta` metrics, sources, or incidents.

### Act 2: Local Egress-Proof & Secret Redaction (1:00 – 2:00)
- **Goal:** Show that synthetic secrets are completely stripped before wire egress (Requirement `PRIV-01`–`PRIV-05`, Check `V03`).
- **Action:** Run Scenario 1 and show the masked local preview and exact outbound body.
- **Evidence:** Compare the left panel (raw input) with the right panel (wire metadata). Observe that raw text is dropped, source hostnames are HMAC-pseudonymized, and the SHA-256 body hash of outbound bytes matches the SaaS receipt confirmation exactly.

### Act 3: Network Outage & Durable Buffering (2:00 – 3:00)
- **Goal:** Demonstrate continuous local buffering and idempotent recovery during network loss (Requirements `BUFF-01`, `IDEM-01`–`IDEM-03`, Checks `V04`, `V09`).
- **Action:** Trigger the simulated 30-second transport cut. Show that telemetry generation continues locally, filling the bounded SQLite outbox.
- **Evidence:** Restore connection. Watch the outbox drain. SaaS receives all events without loss or duplication; replay cannot overwrite current health states.

### Act 4: Explainable AIOps & Alert Storm Correlation (3:00 – 4:00)
- **Goal:** Demonstrate statistical anomaly detection and topological alert grouping (Requirements `AIOP-01`–`AIOP-05`, Checks `V07`, `V08`).
- **Action:** Inject CPU anomaly and network degradation on `lb-01`.
- **Evidence:** Observe the incident detail card:
  - Exact observed vs baseline mean and standard deviation.
  - Transparent heuristic evidence score (no ungrounded AI hallucination).
  - In Scenario 6, related alerts share one incident and the independent worker's alert stays separate.

### Act 5: Policy-Guarded Remediation & Rehearsed Rollback (4:00 – 5:00)
- **Goal:** Demonstrate safe simulated container scaling with operator approval and rollback (Requirements `AUTO-01`–`AUTO-03`, Check `V11`).
- **Action:** Click "Approve Proposal" for `SCALE_CONTAINER_MEMORY` on `api-01`.
- **Evidence:**
  - The central audit records the action ID, actor and execution time. The snapshot stays local.
  - Fresh telemetry shows memory pressure immediately drops.
  - Click "Rollback": container restores initial snapshot state and telemetry returns to baseline.

---

## 3. Disclosures & Known Limitations (Honest Reporting)

1. **Organizer Telemetry Stream:**
   - If an official live organizer data feed was not provided during the event, the system operates in explicit, labelled `DEMO_FALLBACK` mode via `backend/collector/adapters/organizer_adapter.py`.
2. **Remediation Target Scope:**
   - Simulated remediation (`SCALE_CONTAINER_MEMORY`) strictly mutates deterministic demo container states; it does not invoke host Docker/Kubernetes daemons.
3. **Data Residency:**
   - Multi-region routing is enforced via tenant credential tags and assigned-region metadata validation; cross-continental physical multi-region cloud hosting is a documented design target rather than a live multi-datacenter deployment.
