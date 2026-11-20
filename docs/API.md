# Cicada REST API Specification

This specification documents all public and internal REST endpoints across both the **Tier 1 Customer Local Collector** and the **Tier 2 Central SaaS Platform**.

---

## Tier 1: Customer Local Collector APIs

The local collector exposes loopback-only HTTP endpoints bound to `127.0.0.1:9001` (or configured collector port). These endpoints are inaccessible from external networks and provide local auditability.

### 1. GET `/api/local/status`

Requires `Authorization: Bearer <local_token>`. Returns `retained_previews`, `buffering` (`enabled`), pending `queue_depth`, `capacity`, `backpressure`, `quarantine_count`, up to 20 `quarantine_items`, and `session_receipts` with accepted and duplicate counts since collector startup. Queue depth excludes quarantined records. Capacity includes them. A zero depth alone is not delivery evidence.

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
Returns current health for the authenticated tenant. A collector appears after its first accepted heartbeat. A source with historical telemetry only is Poor and reports `no_live_telemetry`. Old replays do not replace a live health sample.

* **Auth:** Bearer Token (Role: `operator`)
* **Response Body (`200 OK`):**
  ```json
  {
    "collectors": [
      {
        "collector_id": "col-us-east-01",
        "health": "Excellent",
        "reasons": ["nominal"],
        "last_heartbeat_utc": "2026-11-20T14:30:00Z",
        "version": "0.1.0",
        "config_status": "valid",
        "cpu_pct": 2.1,
        "queue_depth": 0,
        "rss_mb": 48.5
      }
    ],
    "sources": [
      {
        "source_id": "src-14dc2d2f7dd0e59e7342dcf858246b98",
        "collector_id": "col-us-east-01",
        "health": "Good",
        "reason_codes": ["cpu"],
        "latest_event_time_utc": "2026-11-20T14:30:00Z",
        "last_received_at_utc": "2026-11-20T14:30:00.100Z",
        "payload_uuid": "f47ac10b-58cc-5372-a567-0e02b2c3d479",
        "metrics": {
          "cpu_pct": 72.0,
          "memory_pct": 68.1,
          "disk_used_pct": 50.0,
          "latency_ms": 12.4,
          "packet_loss_pct": 0.0,
          "service_available": true,
          "connectivity": true,
          "disk_read_bps": null,
          "disk_write_bps": null,
          "net_tx_bps": null,
          "net_rx_bps": null
        }
      }
    ],
    "server_time_utc": "2026-11-20T14:30:01Z"
  }
  ```

---

#### GET `/api/v1/transitions`
Returns health state changes newest first, with UTC observation timestamps and reasons.

* **Auth:** Bearer Token (Role: `operator`)
* **Query Parameters:** `cursor` (use the previous `next_cursor`), `limit` (1–200, default 50)
* **Response Body (`200 OK`):**
  ```json
  {
    "items": [
      {
        "transition_id": "104",
        "entity_id": "src-14dc2d2f7dd0e59e7342dcf858246b98",
        "entity_type": "source",
        "from_state": "Good",
        "to_state": "Fair",
        "reason_codes": ["latency"],
        "timestamp_utc": "2026-11-20T14:28:15Z"
      }
    ],
    "next_cursor": null
  }
  ```

---

### 3. AIOps & Incident Endpoints

#### GET `/api/v1/incidents`
Lists active and resolved incidents for the authenticated tenant.

* **Auth:** Bearer Token (Role: `operator`)
* **Query Parameters:** `cursor` (use the previous `next_cursor`), `limit` (1–200, default 50)
* **Response Body (`200 OK`):**
  ```json
  {
    "items": [
      {
        "incident_id": "67aa850c-22d3-4c63-aeb2-60cbc68eb54b",
        "template_title": "Infrastructure anomaly",
        "severity": "warning",
        "status": "open",
        "evidence_score": 30,
        "created_at_utc": "2026-11-20T14:25:00Z",
        "source_ids": ["src-14dc2d2f7dd0e59e7342dcf858246b98"]
      }
    ],
    "next_cursor": null
  }
  ```

---

#### GET `/api/v1/incidents/{id}`
Returns granular explanation and contributing signals for a specific incident.

* **Auth:** Bearer Token (Role: `operator`)
* **Response Body (`200 OK`):**
  ```json
  {
    "incident_id": "67aa850c-22d3-4c63-aeb2-60cbc68eb54b",
    "template_title": "Infrastructure anomaly",
    "severity": "warning",
    "status": "open",
    "created_at_utc": "2026-11-20T14:25:00Z",
    "source_ids": ["src-14dc2d2f7dd0e59e7342dcf858246b98"],
    "alert_ids": ["544052a8-57e9-4742-b7be-044e06412a15"],
    "likely_cause": "The flagged metrics identify where to investigate. No upstream cause is established by the observed signals.",
    "evidence_score": 30,
    "score_method": "Heuristic: min(100, 30 × min(distinct metrics, 2) + 20 × configured dependency + 20 × temporal order)",
    "contributing_signals": [
      {
        "payload_uuid": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
        "source_id": "src-14dc2d2f7dd0e59e7342dcf858246b98",
        "metric": "memory_pct",
        "observed": 94.2,
        "baseline_mean": 62.1,
        "baseline_std": 4.5,
        "z_score": 7.13,
        "event_time_utc": "2026-11-20T14:24:50Z"
      }
    ],
    "reasoning_steps": ["1 persisted alert signals from 1 monitored sources.", "Score inputs: 1 distinct metrics, dependency=0, temporal order=0."],
    "recommended_action": "Inspect the flagged metrics and compare the affected services with their dependencies.",
    "proposal_status": "none"
  }
  ```

---

### 4. Remediation & Rollback Endpoints

#### POST `/api/v1/incidents/{id}/proposal`

An operator requests the fixed playbook for an active memory incident on an allowed demo source. The request body is empty. Repeating the request returns the existing proposal.

#### POST `/api/v1/remediation/{id}/approve`
Rechecks policy and queues the approved simulation. The request body is empty. Approval leaves the action pending until the collector returns its result.

* **Auth:** Bearer Token (Role: `operator`)
* **Response Body (`200 OK`):**
  ```json
  {
    "action_id": "2452117f-e08e-4a10-824b-92a6fc3588e2",
    "incident_id": "67aa850c-22d3-4c63-aeb2-60cbc68eb54b",
    "status": "approved",
    "target_source_id": "src-14dc2d2f7dd0e59e7342dcf858246b98",
    "playbook": "SCALE_CONTAINER_MEMORY",
    "factor": 1.5,
    "simulation": true,
    "policy_verdict": "demo_policy_allowed",
    "reason_code": "queued_scale"
  }
  ```

---

#### POST `/api/v1/remediation/{id}/rollback`
Queues a snapshot rollback for a successful demo action. The request body is empty. The initial response has `status: rollback_pending`. It uses the same response shape as approval.

#### GET `/api/v1/remediation/audit`

Operator only. Returns audit `items` newest first with an optional `next_cursor`. Each item includes the actor, action and incident IDs, target, previous and current status, policy verdict, reason, and UTC occurrence time.

#### GET `/api/v1/collector/commands`

Collector only. Returns pending command `items` scoped to the authenticated collector and its allowed demo sources. Each command includes the fixed playbook, factor, action and command IDs, tenant, target, and `scale` or `rollback`.

#### POST `/api/v1/collector/commands/{id}/result`

Collector only. Accepts the typed result for a dispatched command, including `simulation: true`, outcome, reason code, and before and after simulated capacity on success. Repeating an identical result is idempotent. A conflicting result returns 409.

---

### 5. Performance Benchmarking Endpoints

#### POST `/api/v1/benchmarks/render`
Registers client-side first visible render timing for latency evaluation (`V10`).

* **Auth:** Bearer Token (Role: `operator`)
* **Request Body:**
  ```json
  {
    "run_id": "bench-01",
    "session_id": "browser-a",
    "payload_uuid": "f47ac10b-58cc-5372-a567-0e02b2c3d479",
    "rendered_at_utc": "2026-11-20T14:30:02.120Z"
  }
  ```
* **Response Body (`200 OK`):**
  ```json
  {
    "accepted": true,
    "first_recorded": true
  }
  ```

#### GET `/api/v1/benchmarks`

Operator only. Accepts `run_id` (default `default-run`) and an optional `session_id`. The five-minute window uses the SaaS receive time of approved payloads. It reports `live`, `replay_or_delayed`, and `all` cohorts with eligible, missing, clock-flagged, and valid counts and nearest-rank p50/p95 in milliseconds. Historical records and records received at least 10 seconds after event time are in the replay or delayed cohort. The response also includes measured offline observations. `alert_delay_ms` is the p95 from breach event time to the creation time recorded by the alert's committed transaction. `alert_timing` reports valid and clock-flagged counts for the tenant, across dashboard sessions in the window.
