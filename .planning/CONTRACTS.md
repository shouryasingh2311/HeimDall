# Shared contracts v1

Owner M1. Freeze before parallel implementation. M2/M3 propose interface changes through their status files; never rename independently. M1 generates Pydantic/OpenAPI definitions and metadata-only fixtures at the first checkpoint. Scope: planned v1 interface specifications.

## Local-only input

RawEvent: source_key, stable input_id, event_time_utc, source_timezone, kind (metric/auth), typed metric candidates, optional raw_text/source_ip/username/auth_success. Raw fields never appear in SaaS contracts. Adapter interface: async events() yields RawEvent. JSONL/file first; actual organizer protocol when confirmed. Malformed input creates visible diagnostic count/run failure.

M1 maps raw source names to configured pseudonyms with persistent tenant-local HMAC key. HMAC is not reversible; a separately private local lookup supports mapping when needed.
Payload UUIDv5 uses tenant/collector/source/input_id/event kind. Organizer ID or persisted run/source sequence provides input_id. Two events at the same timestamp must still have distinct input IDs. Restart/retry preserves ID.

## MetadataPayload (strict nested schema)

All models forbid extras, including nested models. No unrestricted metric dictionaries, labels, raw text or free-form context. All numeric values finite.

| Field | Rule |
|---|---|
| schema_version | literal 1 |
| policy_version | configured metadata-v1 |
| payload_uuid | UUID string |
| tenant_id, collector_id | configured; verified against credential |
| source_id | configured opaque pseudonym; collector membership checked |
| region | configured assigned region |
| event_time_utc | RFC3339 UTC ending Z |
| source_timezone | valid IANA timezone |
| event_type | metric or auth_threat |
| metrics | typed Metrics for metric event, otherwise null |
| security | typed SecuritySummary for auth_threat, otherwise null |
| severity | info/warning/critical, from rule/config |

Metrics: cpu_pct, memory_pct, disk_used_pct (0..100); disk_read_bps, disk_write_bps, net_tx_bps, net_rx_bps, latency_ms (>=0); packet_loss_pct (0..100); service_available, connectivity (boolean). Null indicates an unavailable metric; zero is reserved for measured zero values. At least one valid metric required; configured expected signals determine missing-data handling.
SecuritySummary: failed_attempts_count >=5, window_seconds=10, risk_score 0..100, attacker_id pseudonym. No original IP, credentials, SQL, PID or raw authentication context.

CollectorHeartbeat: schema_version, tenant_id, collector_id, region, heartbeat_uuid, generated_at_utc, source_timezone, version (bounded config string), rss_mb, cpu_pct, queue_depth, config_status (valid/invalid). Server owns received_at. Heartbeats are not replayed from the telemetry outbox. Reject duplicate UUID for liveness refresh, age >15s or future >5s. Source membership is separate configured data.

## Canonical bytes and ACK

Serialize UTF-8 JSON with sorted keys, compact separators and finite numbers once; save/send the same bytes. SHA256 is of actual application body bytes, excluding transport framing; SaaS must not reserialize before computing receipt hash.

IngestReceipt: payload_uuid, status (accepted/duplicate), body_sha256, received_at_utc, analysis_status (live/historical/warming_up). HTTP 200 only after commit. 401 invalid credential; 403 identity/role/region mismatch; 409 same ID/different body; 422 invalid schema. Quarantine invalid/conflict records visibly; retry network/5xx. Do not delete quarantine records as delivered.

## SaaS APIs

All except healthz require role and identity-derived tenant scope. Lists return items/next_cursor with limit <=200 and opaque cursor. No local raw-data endpoint exists here.

| Route | Role | Result |
|---|---|---|
| GET /healthz | public | process status only |
| POST /api/v1/ingest/{region} | collector | one MetadataPayload -> IngestReceipt |
| POST /api/v1/heartbeats | collector | fresh heartbeat ACK |
| GET /api/v1/fleet | operator | collectors and sources |
| GET /api/v1/sources/{id}/metrics | operator | sorted historical metadata |
| GET /api/v1/transitions | operator | UTC state/reason history |
| GET /api/v1/payloads/{uuid} | operator | approved body, digest, times, analysis_status |
| GET /api/v1/incidents | operator | incident summaries |
| GET /api/v1/incidents/{id} | operator | IncidentDetail |
| POST /api/v1/incidents/{id}/proposal | operator | pending typed demo proposal |
| POST /api/v1/remediation/{id}/approve | operator | recheck policy; enqueue once |
| POST /api/v1/remediation/{id}/rollback | operator | require success/snapshot; enqueue once |
| GET /api/v1/remediation/audit | operator | chronological action history |
| GET /api/v1/collector/commands | collector | only own commands |
| POST /api/v1/collector/commands/{id}/result | collector | typed idempotent safe result |
| POST /api/v1/benchmarks/render | operator | first-render receipt |
| GET /api/v1/benchmarks | operator | counts, p50/p95, alert/offline delays and timing flags |
| POST /api/v1/scenario-results | collector | typed safe verification summary |
| GET /api/v1/scenario-results | operator | safe observed results |

Fleet source: source_id, collector_id, health (Excellent/Good/Fair/Poor), reason_codes, latest_event_time_utc, last_received_at_utc, metrics. Collector: collector_id, health, reasons, last_heartbeat_utc, version, rss_mb, cpu_pct, queue_depth, config_status.
IncidentDetail: incident_id, severity, status (open/recovering/resolved), template title, source_ids, alert_ids, likely_cause, evidence_score, score_method, contributing_signals, reasoning_steps, recommended_action, proposal_status.
Signal: payload_uuid, source_id, metric, observed, baseline_mean, baseline_std, z_score, event_time_utc; missing stats are null. Explanations cite only signals/configured dependencies.

Phase 5 groups fresh infrastructure alerts by configured tenant dependency group and a 60-second event-time window. Fresh auth failures count locally per source and origin within 10 seconds. The typed auth summary uses a separate incident category. Infrastructure incidents recover after five consecutive normal samples per affected source for every affected metric. A new grouped alert resets recovery. Security incidents stay open pending a verified recovery signal.

ActionProposal: action_id, incident_id, target_source_id, playbook=SCALE_CONTAINER_MEMORY, factor=1.5, simulation=true, policy_verdict, reason_code, status.
Lifecycle: proposed -> approved -> executing -> succeeded/failed; succeeded -> rollback_pending -> rolled_back/rollback_failed. Duplicate approvals/rollbacks return existing state. Require operator role. One active action/target; maximum three NEW actions/hour/tenant/target; rollback excluded from quota. Local snapshot and command receipt persisted with demo state. No real-source execution.

## Local APIs and simulator

Loopback GET /api/local/audit returns bounded raw preview, approved bytes, ID, digest and sent/ACK status. GET /api/local/status returns queue/transport state. POST /api/local/scenarios/{1..8} accepts run_id/seed. POST /api/local/reset only resets completed demo fixtures after pending deliveries/actions finish.
Local APIs require a per-run session token, exact Host/Origin allow-list, no wildcard CORS and escaped text rendering. Token never goes in URL. M3 writes presentation; M1 owns all endpoint/security plumbing.

DemoSource methods: tick(now_utc), inject(scenario_id, seed), snapshot(), restore(snapshot), apply_scale(factor). Modify input state only, never SaaS incidents, receipts or PASS status. M1 wraps command authorization/persistence. FaultTransport wrapper injects disconnect/delay/duplicate/reorder only in demo/test mode. Organizer mode disables these mutation controls.

ScenarioResult: run_id, scenario_id, status (running/passed/failed/blocked), started_at_utc, finished_at_utc, checks (fixed check-name enum; boolean/number/null actual/expected), payload_uuids, incident_ids, missing_ids, duplicate_count, bounded reason_code. No free-form error/log blobs. Raw local inspection stays local; central summary carries approved IDs/counters only.

## UI and timing

M2 uses one API wrapper, 2s polling, cancelled overlapping requests and honest disconnected/stale state. Capture first visible rendering of each payload ID after React commit/frame scheduling; submit run_id/session_id/payload_uuid/rendered_at_utc once. Do not measure fetch completion or every poll. Label browser timing resolution and clock uncertainty. M1 checks referenced IDs belong to operator tenant. This records browser render timing and does not produce cryptographic proofs.

Metadata-only fixtures require permanent MOCK banner. API errors never silently substitute fixture data. Tenant credential change clears cached data/render keys. Live acceptance uses real API only.
