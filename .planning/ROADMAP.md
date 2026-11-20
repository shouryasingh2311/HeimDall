# Roadmap: Cicada AIOps Observability Platform

## Milestone v1.0: Hackathon MVP & Judge Validation Suite

**Milestone Goal:** Deliver a complete, deploy-anywhere, two-tier AIOps observability platform with local-first data protection, Egress Proof verification, durable offline buffering, explainable AIOps correlation, and full coverage of all 4 hackathon judging checkpoints and 8 live validation scenarios.

---

### Phase 1: Two-Tier Core Architecture & Secure Transport
**Goal:** Establish the Tier 1 Local Collector daemon and Tier 2 Central Multi-Tenant SaaS platform with token/TLS authentication and regional endpoint routing.
**Requirements:** ARCH-01, ARCH-02, ARCH-03, ARCH-04
**Success Criteria:**
1. Local collector connects to SaaS ingest endpoint with cryptographic token authentication.
2. Multi-tenant isolation verified by sending telemetry under distinct tenant IDs with complete partition separation.
3. Regional ingest routing correctly maps requests by region header (`us-east-1`, `eu-west-1`, `ap-south-1`).

### Phase 2: Local Privacy Pipeline & Egress Proof Panel
**Goal:** Implement client-side secret scrubbing (passwords, tokens, API keys), field allow-listing, pseudonymization, and the tamper-evident Egress Proof UI.
**Requirements:** PRIV-01, PRIV-02, PRIV-03, PRIV-04, PRIV-05
**Success Criteria:**
1. Raw logs containing secrets (e.g. AWS keys, passwords, bearer tokens) are scrubbed before any network call.
2. Any property not explicitly listed in metadata allow-list is dropped.
3. Egress Proof Panel renders a live audit log displaying exact pre-scrub raw telemetry alongside post-scrub egress payload.

### Phase 3: Resilient Offline Buffering & Idempotent Ingestion
**Goal:** Implement local SQLite WAL outage buffer with exponential backoff retry and SaaS-side idempotent deduplication with UTC event-time indexing.
**Requirements:** BUFF-01, BUFF-02, IDEM-01, IDEM-02, IDEM-03
**Success Criteria:**
1. During simulated SaaS outage, collector buffers all approved metadata into SQLite without memory bloat or crash.
2. When SaaS reconnects, all buffered records are drained and delivered with zero record loss.
3. Out-of-order and replayed duplicate payloads are de-duplicated by UUID with zero duplicates stored.

### Phase 4: Telemetry Metrics Engine, Health States & Benchmarking
**Goal:** Ingest infrastructure/network metrics, evaluate 4 operational health states (Excellent, Good, Fair, Poor), and enforce real-time performance targets.
**Requirements:** METR-01, METR-02, HLTH-01, HLTH-02, HLTH-03, PERF-01, PERF-02, PERF-03
**Success Criteria:**
1. Real-time metric ingestion tracks CPU, RAM, disk, network bandwidth, latency, and packet loss.
2. System health dynamically updates across `Excellent`, `Good`, `Fair`, `Poor` based on configurable baselines.
3. Stale data (>30s) automatically degrades health status instead of holding last good value.
4. Measured collection-to-dashboard latency is $\le 10$s at p95; collector offline detection triggers within 60s.

### Phase 5: Explainable AIOps Anomaly Detection & Incident Correlation
**Goal:** Develop dynamic baselining (EWMA / Z-score), local security attack scoring, multi-signal alert correlation, and transparent reasoning path generation.
**Requirements:** AIOP-01, AIOP-02, AIOP-03, AIOP-04, AIOP-05
**Success Criteria:**
1. AIOps flags anomalies when metrics deviate from dynamic baseline, ignoring normal non-anomalous spikes.
2. Local security analysis detects repeated failed logins and emits risk score without transmitting credentials.
3. Alert correlation engine groups related alerts across systems/services into single root-cause incidents.
4. Each incident outputs explainable recommendations with contributing signals, baseline deltas, confidence score, and reasoning path.

### Phase 6: Autonomous Ops Simulator & Policy-Guarded Remediation
**Goal:** Build the human-in-the-loop autonomous remediation system with policy validation, execution simulation, and rollback controls.
**Requirements:** AUTO-01, AUTO-02, AUTO-03
**Success Criteria:**
1. Recommendation engine suggests contextual remediation action for incidents.
2. Policy gate blocks unapproved action until operator explicitly clicks approve.
3. Remediation execution is logged to audit trail with a verifiable simulated rollback plan.

### Phase 7: Interactive Chaos Engine & 8 Live Validation Scenarios
**Goal:** Create the unified test harness and synthetic stream generator with 1-click execution for all 8 hackathon evaluation scenarios.
**Requirements:** SIMU-01, SIMU-02, SIMU-03, SIMU-04, SIMU-05, SIMU-06, SIMU-07, SIMU-08, SIMU-09
**Success Criteria:**
1. Realistic multi-node telemetry stream runs continuously.
2. Single-click trigger validates each of the 8 mandatory scenarios (raw secret scrub, SaaS outage buffer, brute-force security scoring, latency spike, CPU baseline deviation, alert correlation storm, out-of-order duplicate delivery, safe remediation).

### Phase 8: Unified Operations Dashboard & Judge Verification Suite
**Goal:** Deliver the unified responsive dashboard featuring side-by-side comparison, fleet health visualizers, incident drill-down, and live demo controls.
**Requirements:** DASH-01, DASH-02, DASH-03, DASH-04
**Success Criteria:**
1. Dashboard displays real-time health badges, latency gauges, and collector fleet status.
2. Side-by-side view visually proves raw secret on collector vs. redacted metadata on SaaS.
3. 1-click scenario runner triggers and verifies judge scenarios on the spot.

---
*Roadmap defined: 2026-11-20*