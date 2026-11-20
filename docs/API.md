# Cicada REST API Specification

This specification documents all public and internal REST endpoints across both the **Tier 1 Customer Local Collector** and the **Tier 2 Central SaaS Platform**.

---

## Tier 1: Customer Local Collector APIs

The local collector exposes loopback-only HTTP endpoints bound to `127.0.0.1:9001` (or configured collector port). These endpoints are inaccessible from external networks and provide local auditability.

### 1. GET `/api/local/status`

Requires `Authorization: Bearer <local_token>`. Returns `retained_previews` (count) and `buffering` (`not_enabled` in Phase 2).

### 2. GET `/api/local/audit`

Requires the same local session token. Returns an `items` array with up to 20 recent entries, newest first. Provide an optional `payload_uuid` query parameter to fetch one retained entry. The API returns 400 for an invalid UUID and 404 for an absent or expired UUID.

Each entry includes `payload_uuid`, `policy_version`, `raw_preview` (local text with known credentials masked, or null), `approved_body` (exact outbound JSON as a string), `body_sha256`, `state`, and `receipt` (null until acknowledged). The preview buffer retains up to 500 entries for 15 minutes.

### 3. POST `/api/local/scenarios/{id}`
Triggers an automated scenario injection on the local demo source.

* **Path Parameters:** `id` (int, 1 to 8)
* **Request Body:**
  ```json
  {
    "run_id": "run-20261120-001",
    "seed": 42
  }
  ```
* **Response Body (`200 OK`):**
  ```json
  {
    "status": "injected",
    "scenario_id": 1,
    "run_id": "run-20261120-001"
  }
  ```

---

## Tier 2: Central SaaS Platform APIs

The central platform operates on `https://127.0.0.1:8443` (TLS 1.3). All endpoints except `/healthz` require Bearer token authentication in the `Authorization` header.

### 1. Ingestion Endpoints

#### POST `/api/v1/ingest/{region}`
Ingests a single verified metadata payload from an authenticated collector.

* **Auth:** Bearer Token (Role: `collector`)
* **Request Headers:**
  * `Authorization: Bearer <collector_token>`
  * `Content-Type: application/json`
* **Request Body (`MetadataPayload`):**
  ```json
  {
    "schema_version": 1,
    "policy_version": "metadata-v1",
    "payload_uuid": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
    "tenant_id": "tenant-alpha",
    "collector_id": "col-us-east-01",
    "source_id": "node-db-01",
    "region": "us-east",
    "event_time_utc": "2026-11-20T14:30:00Z",
    "source_timezone": "America/New_York",
    "event_type": "metric",
    "metrics": {
      "cpu_pct": 45.2,
      "memory_pct": 68.1,
      "disk_used_pct": 82.0,
      "disk_read_bps": 1048576,
      "disk_write_bps": 2097152,
      "net_tx_bps": 524288,
      "net_rx_bps": 1048576,
      "latency_ms": 12.4,
      "packet_loss_pct": 0.0,
      "service_available": true,
      "connectivity": true
    },
    "security": null,
    "severity": "info"
  }
  ```
* **Response Body (`200 OK`):**
  ```json
  {
    "payload_uuid": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
    "status": "accepted",
    "body_sha256": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
    "received_at_utc": "2026-11-20T14:30:01Z",
    "analysis_status": "live"
  }
  ```
* **Status Codes:**
  * `200 OK`: Ingestion committed or recognized as duplicate.
  * `401 Unauthorized`: Invalid Bearer token.
  * `403 Forbidden`: Collector region or tenant ID does not match token claim.
  * `409 Conflict`: Payload UUID exists with a different body digest.
  * `422 Unprocessable Entity`: Validation failure (unknown field or out-of-range numeric).

---

#### POST `/api/v1/heartbeats`
Transmits collector liveness and health metadata.

* **Auth:** Bearer Token (Role: `collector`)
* **Request Body:**
  ```json
  {
    "schema_version": 1,
    "tenant_id": "tenant-alpha",
    "collector_id": "col-us-east-01",
    "region": "us-east",
    "heartbeat_uuid": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
    "generated_at_utc": "2026-11-20T14:30:00Z",
    "source_timezone": "America/New_York",
    "version": "1.0.0",
    "rss_mb": 48.5,
    "cpu_pct": 1.2,
    "queue_depth": 0,
    "config_status": "valid"
  }
  ```
* **Response Body (`200 OK`):**
  ```json
  {
    "status": "acknowledged",
    "received_at_utc": "2026-11-20T14:30:00Z"
  }
  ```

---

### 2. Fleet & Health Endpoints

#### GET `/api/v1/fleet`
Returns current operational status of all collectors and sources for the authenticated tenant.

* **Auth:** Bearer Token (Role: `operator`)
* **Response Body (`200 OK`):**
  ```json
  {
    "collectors": [
      {
        "collector_id": "col-us-east-01",
        "health": "Excellent",
        "reasons": ["HEARTBEAT_OK", "QUEUE_EMPTY"],
        "last_heartbeat_utc": "2026-11-20T14:30:00Z",
        "queue_depth": 0,
        "rss_mb": 48.5
      }
    ],
    "sources": [
      {
        "source_id": "node-db-01",
        "collector_id": "col-us-east-01",
        "health": "Good",
        "reasons": ["METRICS_NORMAL"],
        "latest_event_time_utc": "2026-11-20T14:30:00Z",
        "latest_metrics": {
          "cpu_pct": 45.2,
          "memory_pct": 68.1,
          "latency_ms": 12.4
        }
      }
    ]
  }
  ```

---

#### GET `/api/v1/transitions`
Retrieves chronological health state transition records with reason codes.

* **Auth:** Bearer Token (Role: `operator`)
* **Query Parameters:** `source_id` (optional), `limit` (int, default 50)
* **Response Body (`200 OK`):**
  ```json
  {
    "transitions": [
      {
        "transition_id": 104,
        "source_id": "node-db-01",
        "from_state": "Good",
        "to_state": "Fair",
        "reason_code": "WARN_ELEVATED_LATENCY",
        "timestamp_utc": "2026-11-20T14:28:15Z"
      }
    ]
  }
  ```

---

### 3. AIOps & Incident Endpoints

#### GET `/api/v1/incidents`
Lists active and resolved incidents for the authenticated tenant.

* **Auth:** Bearer Token (Role: `operator`)
* **Response Body (`200 OK`):**
  ```json
  {
    "incidents": [
      {
        "incident_id": "inc-20261120-01",
        "title": "Correlated Memory & Latency Spike",
        "severity": "critical",
        "status": "open",
        "evidence_score": 88,
        "created_at_utc": "2026-11-20T14:25:00Z",
        "source_ids": ["node-app-01", "node-db-01"]
      }
    ]
  }
  ```

---

#### GET `/api/v1/incidents/{id}`
Returns granular explanation and contributing signals for a specific incident.

* **Auth:** Bearer Token (Role: `operator`)
* **Response Body (`200 OK`):**
  ```json
  {
    "incident_id": "inc-20261120-01",
    "title": "Correlated Memory & Latency Spike",
    "severity": "critical",
    "status": "open",
    "likely_cause": "Memory exhaustion on node-app-01 cascading to db query timeout",
    "evidence_score": 88,
    "score_method": "z_score_composite_v1",
    "contributing_signals": [
      {
        "payload_uuid": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
        "source_id": "node-app-01",
        "metric": "memory_pct",
        "observed": 94.2,
        "baseline_mean": 62.1,
        "baseline_std": 4.5,
        "z_score": 7.13,
        "event_time_utc": "2026-11-20T14:24:50Z"
      }
    ],
    "recommended_action": "SCALE_CONTAINER_MEMORY",
    "proposal_status": "proposed"
  }
  ```

---

### 4. Remediation & Rollback Endpoints

#### POST `/api/v1/remediation/{id}/approve`
Authorizes an assisted autonomous remediation action.

* **Auth:** Bearer Token (Role: `operator`)
* **Response Body (`200 OK`):**
  ```json
  {
    "action_id": "act-20261120-01",
    "incident_id": "inc-20261120-01",
    "status": "approved",
    "target_source_id": "node-app-01",
    "playbook": "SCALE_CONTAINER_MEMORY",
    "enqueued_at_utc": "2026-11-20T14:26:00Z"
  }
  ```

---

#### POST `/api/v1/remediation/{id}/rollback`
Triggers an atomic rollback to the pre-remediation snapshot.

* **Auth:** Bearer Token (Role: `operator`)
* **Response Body (`200 OK`):**
  ```json
  {
    "action_id": "act-20261120-01",
    "status": "rolled_back",
    "target_source_id": "node-app-01",
    "restored_at_utc": "2026-11-20T14:28:00Z"
  }
  ```

---

### 5. Performance Benchmarking Endpoints

#### POST `/api/v1/benchmarks/render`
Registers client-side first visible render timing for latency evaluation (`V10`).

* **Auth:** Bearer Token (Role: `operator`)
* **Request Body:**
  ```json
  {
    "run_id": "bench-01",
    "payload_uuid": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
    "rendered_at_utc": "2026-11-20T14:30:02.120Z"
  }
  ```
* **Response Body (`200 OK`):**
  ```json
  {
    "status": "recorded",
    "delta_ms": 2120
  }
  ```
