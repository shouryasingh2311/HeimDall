/**
 * Shared contracts v1 TypeScript definitions for Cicada Operations Dashboard
 * Strictly adheres to .planning/CONTRACTS.md
 * Never includes raw logs, passwords, IPs, credentials, or unstructured blobs.
 */

export type HealthState = 'Excellent' | 'Good' | 'Fair' | 'Poor';

export type Severity = 'info' | 'warning' | 'critical';

export type AnalysisStatus = 'live' | 'historical' | 'warming_up';

export type ConfigStatus = 'valid' | 'invalid';

export interface Metrics {
  cpu_pct: number | null;
  memory_pct: number | null;
  disk_used_pct: number | null;
  disk_read_bps: number | null;
  disk_write_bps: number | null;
  net_tx_bps: number | null;
  net_rx_bps: number | null;
  latency_ms: number | null;
  packet_loss_pct: number | null;
  service_available: boolean | null;
  connectivity: boolean | null;
}

export interface SecuritySummary {
  failed_attempts_count: number;
  window_seconds: number;
  risk_score: number;
  attacker_id: string; // Pseudonymous identifier only
}

export interface MetadataPayload {
  schema_version: 1;
  policy_version: 'metadata-v1';
  payload_uuid: string;
  tenant_id: string;
  collector_id: string;
  source_id: string;
  region: string;
  event_time_utc: string; // RFC3339 UTC ending Z
  source_timezone: string; // Valid IANA timezone
  event_type: 'metric' | 'auth_threat';
  metrics: Metrics | null;
  security: SecuritySummary | null;
  severity: Severity;
}

export interface FleetSource {
  source_id: string;
  collector_id: string;
  health: HealthState;
  reason_codes: string[];
  latest_event_time_utc: string;
  last_received_at_utc: string;
  metrics: Metrics;
}

export interface FleetCollector {
  collector_id: string;
  health: HealthState;
  reasons: string[];
  last_heartbeat_utc: string;
  version: string;
  rss_mb: number;
  cpu_pct: number;
  queue_depth: number;
  config_status: ConfigStatus;
}

export interface FleetResponse {
  collectors: FleetCollector[];
  sources: FleetSource[];
  server_time_utc: string;
}

export interface IngestReceipt {
  payload_uuid: string;
  status: 'accepted' | 'duplicate';
  body_sha256: string;
  received_at_utc: string;
  analysis_status: AnalysisStatus;
}

export interface PayloadDetail {
  payload_uuid: string;
  tenant_id: string;
  collector_id: string;
  source_id: string;
  region: string;
  event_time_utc: string;
  source_timezone: string;
  event_type: 'metric' | 'auth_threat';
  metrics: Metrics | null;
  security: SecuritySummary | null;
  severity: Severity;
  body_sha256: string;
  received_at_utc: string;
  analysis_status: AnalysisStatus;
}

export interface StateTransition {
  transition_id: string;
  entity_id: string;
  entity_type: 'source' | 'collector';
  from_state: HealthState;
  to_state: HealthState;
  reason_codes: string[];
  timestamp_utc: string;
}

export interface TransitionsResponse {
  items: StateTransition[];
  next_cursor: string | null;
}

export interface ContributingSignal {
  payload_uuid: string;
  source_id: string;
  metric: string;
  observed: number;
  baseline_mean: number | null;
  baseline_std: number | null;
  z_score: number | null;
  event_time_utc: string;
}

export interface IncidentSummary {
  incident_id: string;
  severity: Severity;
  status: 'open' | 'recovering' | 'resolved';
  template_title: string;
  source_ids: string[];
  evidence_score: number; // 0-100 Heuristic evidence score
  created_at_utc: string;
}

export interface IncidentDetail {
  incident_id: string;
  severity: Severity;
  status: 'open' | 'recovering' | 'resolved';
  template_title: string;
  source_ids: string[];
  alert_ids: string[];
  likely_cause: string;
  evidence_score: number; // Heuristic evidence score only, no causal certainty claim
  score_method: string;
  contributing_signals: ContributingSignal[];
  reasoning_steps: string[];
  recommended_action: string;
  proposal_status: 'none' | 'proposed' | 'approved' | 'executing' | 'succeeded' | 'failed' | 'rolled_back';
}

export interface ActionProposal {
  action_id: string;
  incident_id: string;
  target_source_id: string;
  playbook: 'SCALE_CONTAINER_MEMORY';
  factor: number;
  simulation: true; // Hardcoded simulation flag
  policy_verdict: string;
  reason_code: string;
  status: 'proposed' | 'approved' | 'executing' | 'succeeded' | 'failed' | 'rollback_pending' | 'rolled_back' | 'rollback_failed';
}

export interface BenchmarkRenderPayload {
  run_id: string;
  session_id: string;
  payload_uuid: string;
  rendered_at_utc: string;
  dom_commit_duration_ms?: number;
}

export interface BenchmarkRenderResponse {
  accepted: boolean;
  first_recorded: boolean;
}

export interface BenchmarkSummary {
  render_count: number;
  render_p50_ms: number;
  render_p95_ms: number;
  alert_delay_p50_ms?: number;
  alert_delay_p95_ms?: number;
  offline_recovery_seconds?: number;
  timing_flags?: Record<string, boolean>;
}

export interface ScenarioResult {
  run_id: string;
  scenario_id: number;
  status: 'running' | 'passed' | 'failed' | 'blocked';
  started_at_utc: string;
  finished_at_utc: string;
  checks: Record<string, boolean | number | null>;
  payload_uuids: string[];
  incident_ids: string[];
  missing_ids: string[];
  duplicate_count: number;
  reason_code?: string;
}

export interface ApiClientConfig {
  baseUrl: string;
  tenantId: string;
  operatorToken?: string;
}
