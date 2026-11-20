# Architecture & Trust Boundaries

This document provides a deep architectural breakdown of **Heimdal**, its two-tier deployment model, trust boundaries, cryptographic verification, persistent storage engine, and AIOps pipeline.

---

## 1. Two-Tier Deployment Topology

Heimdal separates data collection from centralized analysis across physical and network trust boundaries:

```
+-------------------------------------------------------------------------+
|                  TIER 1: CUSTOMER LOCAL ENVIRONMENT                     |
|                                                                         |
|  [ Local Telemetry Sources ]                                            |
|   - Host metrics, container stats, syslog, auth logs                    |
|                |                                                        |
|                v                                                        |
|  [ Collector Daemon ] (Loopback HTTP: 127.0.0.1:9001)                   |
|   +------------------------------------------------------------------+  |
|   | 1. Input Adapter: Maps raw inputs to internal RawEvent           |  |
|   | 2. Security Sanitizer: Regex scrubbing + nested allow-listing    |  |
|   | 3. Pseudonymizer: Salted HMAC for source identity                |  |
|   | 4. Serialization: Canonical JSON (sorted keys, compact)          |  |
|   | 5. Outbox: SQLite WAL + FULL sync (persist before transmit)      |  |
|   | 6. HTTPX Sender: Verified HTTPS with backoff + jitter            |  |
|   +------------------------------------------------------------------+  |
|        |                                                    ^           |
|        | Local Loopback (HTTP)                              | Loopback  |
|        v                                                    v           |
|  [ Egress Proof Panel ]                            [ Local Preview DB ] |
|   - Bounded ring buffer (500 records / 15 mins)                         |
+-------------------------------------------------------------------------+
                                   |
                      Verified HTTPS (Port 8443)
                      - TLS 1.3 / Strict CA check
                      - Bearer token authentication
                      - Canonical JSON MetadataPayload
                                   |
                                   v
+-------------------------------------------------------------------------+
|                    TIER 2: CENTRAL SAAS PLATFORM                        |
|                                                                         |
|  [ Regional Ingest Endpoint ] (FastAPI / Uvicorn: 8443)                 |
|   +------------------------------------------------------------------+  |
|   | 1. Authenticate Token: Validate role, tenant_id, region          |  |
|   | 2. Ingest Verification: Compute SHA-256 over exact wire bytes    |  |
|   | 3. Strict Schema Validation: Pydantic v2 (extra="forbid")        |  |
|   | 4. Transactional Commit: Unique(tenant_id, payload_uuid)         |  |
|   | 5. Return IngestReceipt: Status, body_sha256, received_at_utc    |  |
|   +------------------------------------------------------------------+  |
|        |                                                                |
|        v                                                                |
|  [ Multi-Tenant Storage (SQLite WAL / FULL) ]                           |
|        |                                                                |
|        +------------------------+-----------------------+               |
|        |                        |                       |               |
|        v                        v                       v               |
|  [ 4-State Health ]     [ AIOps Detector ]    [ Correlator ]            |
|   - Baseline check       - Rolling Z-Score     - Topology graph         |
|   - Staleness watchdog   - Variance floor      - Time window (60s)      |
|   - UTC transition log   - Evidence score      - Grouped incidents      |
|        |                        |                       |               |
|        +------------------------+-----------------------+               |
|                                 |                                       |
|                                 v                                       |
|                    [ SaaS REST Read APIs ]                              |
|                     (Tenant-isolated queries)                           |
|                                 |                                       |
|                                 v 2-Second Polling                      |
|                    [ React Operations Dashboard ]                       |
|                     (Client-side render profiling)                      |
+-------------------------------------------------------------------------+
```

---

## 2. Cryptographic Security & Identity Model

### 2.1 Transport Layer Security (TLS 1.3)
* **Zero Insecure Fallbacks:** Production and development collectors enforce strict TLS verification using a local CA root. `verify=False` is strictly prohibited.
* **Server SAN Verification:** Server certificates include Subject Alternative Names for `localhost`, `127.0.0.1`, and explicit regional hostnames (`us-east.heimdal.local`, `eu-west.heimdal.local`).
* **Client Handshake:** Python's `HTTPX` client verifies both the certificate authority trust chain and server hostname before any payload bytes are transmitted.

### 2.2 Identity & Role-Based Access Control (RBAC)
Every request to the SaaS platform requires a Bearer token cryptographically mapped to an authenticated identity:

```python
class AuthenticatedIdentity:
    role: Literal["collector", "operator"]
    tenant_id: str
    collector_id: Optional[str]
    assigned_region: str
```

* **Tenant Boundary Enforcement:** Every SQL query, baseline calculation, and incident search includes `WHERE tenant_id = :authenticated_tenant`. No UI selector or client header can bypass this scope.
* **Region Affinity:** Ingest requests to `/api/v1/ingest/{region}` must match the collector's configured `assigned_region`. Mismatches are rejected with HTTP `403 Forbidden`.

### 2.3 Pseudonymization
To eliminate the risk of leaking internal network topology or server hostnames:
$$\text{source\_id} = \text{HMAC-SHA256}(\text{source\_key}, \text{tenant\_secret})[:16]$$
* The SaaS tier only knows `source_id` as an opaque hex string.
* Reversible lookup tables remain strictly inside the customer local environment.

---

## 3. Data Sanitization & Egress Proof Engine

### 3.1 Strict Nested Allow-Listing
Unlike platforms that accept free-form JSON payloads or dictionaries, Heimdal rejects extra fields at the Pydantic parser layer:

```python
class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
```

The permitted schema (`MetadataPayload`) allows only:
* `schema_version`: Literal 1
* `payload_uuid`: UUID string
* `tenant_id`, `collector_id`, `source_id`, `region`: String tokens
* `event_time_utc`, `source_timezone`: ISO 8601 UTC string + IANA timezone
* `event_type`: `"metric"` | `"auth_threat"`
* `metrics`: Strongly-typed `Metrics` struct (or `None`)
* `security`: Strongly-typed `SecuritySummary` struct (or `None`)
* `severity`: `"info"` | `"warning"` | `"critical"`

### 3.2 Wire-Level SHA-256 Digest Equality
To prove that what was audited locally is identical to what was stored centrally:
1. Collector serializes the payload once:
   $$\text{wire\_bytes} = \text{json.dumps}(\text{payload}, \text{sort\_keys}=\text{True}, \text{separators}=(',', ':')).\text{encode}('utf-8')$$
2. Collector computes:
   $$\text{body\_sha256} = \text{SHA256}(\text{wire\_bytes})$$
3. SaaS receives raw request bytes, computes $\text{SHA256}(\text{request.body()})$, and verifies equality before inserting into the database.
4. SaaS stores the digest in `ingest_receipts` and returns it in the HTTP response.
5. Operators can verify on the Egress Proof Panel that $\text{Local Digest} \equiv \text{Remote Digest}$.

---

## 4. Durable Outbox & Idempotent Ingestion

### 4.1 Persist-Before-Send Mechanics
To prevent data loss during network partitions, the collector utilizes a local SQLite database configured with:
* `PRAGMA journal_mode = WAL;`
* `PRAGMA synchronous = FULL;`

Every generated telemetry event is inserted into `collector_outbox` in the `PENDING` state before HTTP transmission is attempted:

```sql
CREATE TABLE collector_outbox (
    payload_uuid TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    wire_bytes BLOB NOT NULL,
    body_sha256 TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('PENDING', 'SENT', 'ACKED')),
    created_at_utc TEXT NOT NULL,
    retry_count INTEGER DEFAULT 0
);
```

### 4.2 Idempotent Server Commit
Upon arrival at the central SaaS:
1. An explicit transaction begins: `BEGIN IMMEDIATE;`
2. An insert into `saas_metadata` is attempted:
   ```sql
   INSERT INTO saas_metadata (payload_uuid, tenant_id, source_id, body_sha256, event_time_utc, raw_payload)
   VALUES (?, ?, ?, ?, ?, ?);
   ```
3. **If unique constraint fails:**
   * If `body_sha256` matches existing record: return HTTP `200 OK` with `status: "duplicate"`. No analytics, alerts, or health transitions are recomputed.
   * If `body_sha256` differs: return HTTP `409 Conflict`. Quarantine the invalid record.
4. **If unique constraint succeeds:**
   * Evaluate rolling z-score detector and correlate incidents within the same atomic transaction.
   * Commit transaction: `COMMIT;`
   * Return HTTP `200 OK` with `status: "accepted"`.

---

## 5. Operational Health Engine

The SaaS health engine classifies collectors and monitored sources into four states:

```
┌──────────────┐     Metric Breach     ┌──────────────┐
│  EXCELLENT   │ ────────────────────> │     GOOD     │
└──────────────┘                       └──────────────┘
       │                                      │
       │ Elevated Loss / Latency              │ Sustained Degradation
       v                                      v
┌──────────────┐                       ┌──────────────┐
│     FAIR     │ ────────────────────> │     POOR     │
└──────────────┘     Heartbeat Loss    └──────────────┘
```

* **Severity Precedence:** `POOR` > `FAIR` > `GOOD` > `EXCELLENT`. If any single active metric rule triggers `POOR`, the overall source health drops to `POOR`.
* **Heartbeat Watchdog:** SaaS runs an independent background loop every second. If `now_utc - last_heartbeat_utc > 60s`, collector status immediately transitions to `POOR` with reason code `ERR_HEARTBEAT_TIMEOUT`.
* **Stale Replay Protection:** If an out-of-order or late event arrives with `event_time_utc < latest_source_time`, it is saved for historical trend charts but **cannot** alter the current live health status.

---

## 6. Statistical AIOps & Incident Correlation

### 6.1 Anomaly Detection Engine
Heimdal uses a deterministic rolling z-score algorithm with an adaptive variance floor:
$$z = \frac{x_t - \mu_{t-1}}{\max(\sigma_{t-1}, \sigma_{\text{floor}})}$$
* $\mu_{t-1}$: Rolling mean over the prior $N$ samples ($N \ge 10$ warm-up).
* $\sigma_{t-1}$: Rolling standard deviation over the prior $N$ samples.
* $\sigma_{\text{floor}}$: Prevents division by zero and false alerts when metrics are completely steady.
* **Anomaly Condition:** $|z| \ge 3.0$ triggers an anomalous signal event.

### 6.2 Incident Correlation Engine
When an anomaly signal occurs:
1. The correlator searches for active incidents belonging to the same `tenant_id`.
2. It checks if the source shares a configured **dependency group** (e.g., `web-service-1` depends on `db-cluster-1`).
3. If an active incident exists within the correlation window ($\Delta t \le 60\text{s}$), the new alert is merged into the incident.
4. If no related incident is active, a new incident is created with a unique `incident_id`.
5. **Heuristic Evidence Score ($0..100$):**
   $$\text{Score} = \min\left(100, 40 \times \frac{|z|}{3.0} + 20 \times \text{num\_contributing\_signals} + 20 \times \text{topology\_depth}\right)$$

---

## 7. Policy-Guarded Remediation & Rollback

Heimdal provides an end-to-end audit trail for autonomous remediation:

```
[ Incident Raised ]
        │
        ▼
[ Policy Evaluator ]
  - Checks target eligibility (demo target only)
  - Enforces rate limit (max 3 actions / hour / target)
        │
        ▼
[ Action Proposal ] (playbook: SCALE_CONTAINER_MEMORY, factor: 1.5)
        │
        ▼
[ Operator Approval ] (Requires RBAC operator credential)
        │
        ▼
[ Collector Execution ]
  1. Capture state snapshot: { "memory_limit_mb": 512 }
  2. Apply new capacity: { "memory_limit_mb": 768 }
  3. Emit command execution receipt
        │
        ▼
[ Recovery Telemetry ] (Memory utilization drops on next poll)
        │
        ▼
[ Rollback Option ]
  Operator clicks "Rollback" -> Restores snapshot: { "memory_limit_mb": 512 }
```
