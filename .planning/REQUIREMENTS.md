# Requirements: Cicada AIOps Observability Platform

**Defined:** 2026-11-20
**Core Value:** Zero raw telemetry or credentials leave the customer environment, verified by a local Egress Proof Panel, while the SaaS platform delivers real-time, explainable AIOps correlation and actionable operational recommendations.

## v1 Requirements

Requirements for the 24-hour hackathon release covering all 4 evaluation phases and 8 live validation scenarios.

### Two-Tier Architecture & Transport (ARCH)

- [ ] **ARCH-01**: Tier 1 Local Collector runs as an independent lightweight daemon inside the customer environment and communicates exclusively with the Tier 2 SaaS platform.
- [ ] **ARCH-02**: Collector-to-SaaS link is authenticated via cryptographic tokens/certificates and encrypted in transit via TLS.
- [ ] **ARCH-03**: Central SaaS platform enforces strict multi-tenant isolation, ensuring no tenant metadata can ever be accessed by another tenant.
- [ ] **ARCH-04**: Global-ready regional ingest routing directs collector metadata to assigned regional endpoints (`us-east-1`, `eu-west-1`, `ap-south-1`) respecting data residency policies.

### Local Data Protection & Privacy Egress (PRIV)

- [ ] **PRIV-01**: Local filtering pipeline strips all raw logs, raw payloads, stack traces, and unapproved metrics before transmission.
- [ ] **PRIV-02**: Strict field allow-list mechanism drops any telemetry property not explicitly designated in the approved metadata schema.
- [ ] **PRIV-03**: Regex-driven secret scrubbing automatically detects and redacts credentials, passwords, JWT bearer tokens, AWS/API keys, and connection strings on the local collector.
- [ ] **PRIV-04**: Pseudonymization engine hashes or maps local hostnames, internal IP addresses, and user identifiers to consistent pseudonym tokens before egress.
- [ ] **PRIV-05**: Local Egress Proof Panel provides a real-time, tamper-evident inspection log and web view showing exact pre-scrub vs. post-scrub payload bytes before egress.

### Local Buffering, Outage Recovery & Idempotency (BUFF / IDEM)

- [ ] **BUFF-01**: Local SQLite WAL queue automatically buffers approved metadata payloads whenever the central SaaS endpoint is unreachable.
- [ ] **BUFF-02**: Outage detection triggers automatic exponential backoff retries and resumes transmission upon network restoration with zero record loss.
- [ ] **IDEM-01**: Every outgoing payload carries a unique deterministic UUID based on tenant, source, event timestamp, and type.
- [ ] **IDEM-02**: SaaS ingestion pipeline performs idempotent de-duplication, guaranteeing zero duplicate metrics or incidents during post-outage backlog replay.
- [ ] **IDEM-03**: Telemetry events carry UTC timestamps and source timezones; late or out-of-order records are indexed by event timestamp rather than arrival time.

### Telemetry Ingestion, System Health & Performance (METR / PERF / HLTH)

- [ ] **METR-01**: Ingests CPU, memory, disk I/O, network bandwidth, network latency, and packet loss telemetry.
- [ ] **METR-02**: Tracks collector fleet health, monitoring online/offline status, heartbeat interval, collector version, and resource consumption.
- [ ] **HLTH-01**: Classifies monitored systems and collectors into four discrete health states: `Excellent` (Healthy), `Good` (Normal), `Fair` (Needs Attention), and `Poor` (Critical).
- [ ] **HLTH-02**: Stale or missing data automatically downgrades the operational health state instead of retaining the last known good state.
- [ ] **HLTH-03**: Health state transitions are timestamped in UTC and recorded in an auditable historical transition log.
- [ ] **PERF-01**: Event collection-to-dashboard render latency is maintained within 10 seconds at the 95th percentile.
- [ ] **PERF-02**: Metric threshold breach to alert generation occurs within 15 seconds of condition trigger.
- [ ] **PERF-03**: Collector offline status detection triggers and downgrades system state to `Poor` within 60 seconds of last heartbeat.

### AIOps Dynamic Anomaly Detection & Correlation (AIOP)

- [ ] **AIOP-01**: Dynamic baseline engine computes rolling statistical baselines (EWMA and rolling Z-score/MAD) to identify true anomalies beyond static thresholds.
- [ ] **AIOP-02**: Local security analytics detects repeated failed logins and brute-force bursts locally, emitting a risk indicator score without exporting raw authentication records.
- [ ] **AIOP-03**: Multi-signal event correlation merges related infrastructure, network, and security alerts within a sliding temporal window into a single unified incident.
- [ ] **AIOP-04**: Root-cause analysis engine traces incident impact across dependent components (e.g., latency rise leading to service degradation).
- [ ] **AIOP-05**: Explainable AIOps recommendation generator details exactly which signals contributed, baseline deviation magnitudes, confidence percentage, and reasoning path.

### Autonomous Ops & Safe Remediation Simulation (AUTO)

- [ ] **AUTO-01**: Recommendation engine proposes targeted operational remediation actions (e.g., restart crashed service, scale memory allocation, block malicious source IP).
- [ ] **AUTO-02**: Human-in-the-loop approval workflow enforces explicit operator confirmation before executing any remediation action.
- [ ] **AUTO-03**: Remediation sandbox records an immutable audit log of policy checks, approvals, simulated action execution, and rollback plans.

### Interactive Chaos & Evaluation Scenarios (SIMU)

- [ ] **SIMU-01**: Synthetic stream generator emits continuous realistic infrastructure and application telemetry matching the organizer specification.
- [ ] **SIMU-02**: Scenario 1 Trigger: Injects raw secrets (API keys, DB passwords) into logs to prove local redaction and egress safety.
- [ ] **SIMU-03**: Scenario 2 Trigger: Injects a SaaS network outage to prove local buffering, reconnection, and zero-loss backlog drainage.
- [ ] **SIMU-04**: Scenario 3 Trigger: Injects repeated failed login attacks to prove edge security risk scoring without raw log leakage.
- [ ] **SIMU-05**: Scenario 4 Trigger: Injects network latency spikes and packet loss to demonstrate service impact tracing.
- [ ] **SIMU-06**: Scenario 5 Trigger: Injects abnormal CPU/memory drift to prove dynamic baseline deviation detection.
- [ ] **SIMU-07**: Scenario 6 Trigger: Injects simultaneous cascading alerts to demonstrate multi-signal incident consolidation.
- [ ] **SIMU-08**: Scenario 7 Trigger: Injects duplicate and out-of-order packets to demonstrate idempotent de-duplication.
- [ ] **SIMU-09**: Scenario 8 Trigger: Triggers an automated remediation recommendation with interactive policy approval and rollback.

### Operations Dashboard & Egress Proof UI (DASH)

- [ ] **DASH-01**: Central SaaS Operations Dashboard renders live fleet status, four health state badges, active incidents, and latency metrics.
- [ ] **DASH-02**: Side-by-side verification view displays raw local logs with secrets alongside the sanitized metadata ingested by SaaS.
- [ ] **DASH-03**: Interactive Incident Drill-Down panel displays explainable AIOps reasoning paths, confidence meters, and one-click remediation controls.
- [ ] **DASH-04**: Simulation Control Panel provides 1-click execution for all 8 hackathon live scenarios.

## v2 Requirements

Deferred features for post-hackathon enterprise production.

### Autonomous Ops (Production)
- **AUTO-V2-01**: Automated remediation execution against live Kubernetes clusters and cloud APIs with canaried rollout.
- **AUTO-V2-02**: Reinforcement learning from operator feedback to adjust recommendation confidence.

### Advanced Edge Processing
- **EDGE-V2-01**: eBPF-based kernel-level network tracing and packet loss inspection on Linux nodes.
- **EDGE-V2-02**: Hardware-accelerated local machine learning inference on edge gateway devices.

## Out of Scope

| Feature | Reason |
| :--- | :--- |
| Central raw log lake | Violates local-first privacy directive; raw logs must remain within the customer boundary. |
| Destructive unapproved auto-actions | Unbounded autonomous modification of infrastructure is hazardous; only policy-checked, human-approved simulated actions are supported. |
| Proprietary cloud vendor lock-in | System must run anywhere across bare-metal, private DC, AWS, GCP, Azure, and edge without vendor-specific services. |
| Full enterprise IAM / SSO integration | Standard JWT/API key authentication is sufficient for the 24-hour hackathon scope. |

## Traceability

| Requirement | Phase | Status |
| :--- | :--- | :--- |
| ARCH-01, ARCH-02, ARCH-03, ARCH-04 | Phase 1 | Pending |
| PRIV-01, PRIV-02, PRIV-03, PRIV-04, PRIV-05 | Phase 2 | Pending |
| BUFF-01, BUFF-02, IDEM-01, IDEM-02, IDEM-03 | Phase 3 | Pending |
| METR-01, METR-02, HLTH-01, HLTH-02, HLTH-03 | Phase 4 | Pending |
| PERF-01, PERF-02, PERF-03 | Phase 4 | Pending |
| AIOP-01, AIOP-02, AIOP-03, AIOP-04, AIOP-05 | Phase 5 | Pending |
| AUTO-01, AUTO-02, AUTO-03 | Phase 6 | Pending |
| SIMU-01, SIMU-02, SIMU-03, SIMU-04, SIMU-05, SIMU-06, SIMU-07, SIMU-08, SIMU-09 | Phase 7 | Pending |
| DASH-01, DASH-02, DASH-03, DASH-04 | Phase 8 | Pending |

**Coverage:**
- v1 requirements: 32 total
- Mapped to phases: 32
- Unmapped: 0 ✓

---
*Requirements defined: 2026-11-20*
*Last updated: 2026-11-20 after initial definition*