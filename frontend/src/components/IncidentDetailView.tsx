import React, { useState, useEffect } from 'react';
import type { IncidentSummary, IncidentDetail, ActionProposal, ActionAudit } from '../types/contracts';
import { apiClient } from '../api/client';
import {
  MOCK_INCIDENTS_SUMMARY,
  MOCK_INCIDENT_DETAIL,
  MOCK_ACTION_PROPOSAL,
  MOCK_REMEDIATION_AUDIT,
} from '../fixtures/metadataFixtures';

interface IncidentDetailViewProps {
  isFixtureMode: boolean;
  initialIncidentId?: string;
  onInspectPayload?: (uuid: string) => void;
}

export const IncidentDetailView: React.FC<IncidentDetailViewProps> = ({
  isFixtureMode,
  initialIncidentId,
  onInspectPayload,
}) => {
  const [incidents, setIncidents] = useState<IncidentSummary[]>(
    isFixtureMode ? MOCK_INCIDENTS_SUMMARY : [],
  );
  const [selectedIncidentId, setSelectedIncidentId] = useState<string | null>(
    initialIncidentId || (isFixtureMode ? MOCK_INCIDENTS_SUMMARY[0]?.incident_id || null : null),
  );
  const [detail, setDetail] = useState<IncidentDetail | null>(
    isFixtureMode ? MOCK_INCIDENT_DETAIL : null,
  );
  const [proposal, setProposal] = useState<ActionProposal | null>(
    isFixtureMode ? MOCK_ACTION_PROPOSAL : null,
  );
  const [auditTrail, setAuditTrail] = useState<ActionAudit[]>([]);
  const [actionBusy, setActionBusy] = useState<boolean>(false);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [listError, setListError] = useState<string | null>(null);

  useEffect(() => {
    if (initialIncidentId) {
      setSelectedIncidentId(initialIncidentId);
    }
  }, [initialIncidentId]);

  useEffect(() => {
    if (isFixtureMode) {
      setIncidents(MOCK_INCIDENTS_SUMMARY);
      if (!selectedIncidentId) {
        setSelectedIncidentId(MOCK_INCIDENTS_SUMMARY[0]?.incident_id || null);
      }
      setDetail(MOCK_INCIDENT_DETAIL);
      setProposal(MOCK_ACTION_PROPOSAL);
      setAuditTrail(MOCK_REMEDIATION_AUDIT.map((row, index) => ({
        ...row, audit_id: index, actor: 'Fixture', occurred_at: 'Fixture', previous_status: null,
      })));
      setListError(null);
      return;
    }

    let active = true;
    const fetchIncidents = async () => {
      try {
        const list = await apiClient.getIncidents();
        if (active) {
          setIncidents(list);
          setListError(null);
          if (list.length > 0 && !selectedIncidentId) {
            setSelectedIncidentId(list[0].incident_id);
          }
        }
      } catch (err: unknown) {
        if (active) {
          setIncidents([]);
          setListError((err as Error).message || 'Failed to fetch incidents list from SaaS');
        }
      }
    };

    fetchIncidents();
    const interval = setInterval(fetchIncidents, 5000);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, [isFixtureMode, selectedIncidentId]);

  useEffect(() => {
    if (!selectedIncidentId || isFixtureMode) return;

    let active = true;
    setDetail(null);
    setProposal(null);
    setActionMessage(null);
    const fetchDetail = async () => {
      try {
        const d = await apiClient.getIncident(selectedIncidentId);
        if (active) {
          setDetail(d);
          setProposal(d.proposal ?? null);
        }
      } catch {
        if (active) setDetail(null);
      }
    };

    const fetchAudit = async () => {
      try {
        const audit = await apiClient.getRemediationAudit();
        if (active) setAuditTrail(audit);
      } catch {
        if (active) setAuditTrail([]);
      }
    };

    fetchDetail();
    fetchAudit();
    const timer = window.setInterval(() => {
      void fetchDetail();
      void fetchAudit();
    }, 2000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [selectedIncidentId, isFixtureMode]);

  const handleRequestProposal = async () => {
    if (!detail) return;
    setActionBusy(true);
    setActionMessage('Requesting autonomous remediation proposal from policy engine...');

    if (isFixtureMode) {
      setTimeout(() => {
        setProposal({
          action_id: `act-${detail.incident_id}`,
          incident_id: detail.incident_id,
          target_source_id: detail.source_ids[0] || 'src-payment-proc-01',
          playbook: 'SCALE_CONTAINER_MEMORY',
          factor: 1.5,
          simulation: true,
          policy_verdict: 'APPROVED_BY_POLICY',
          reason_code: 'TARGET_IN_SIMULATION_ALLOWLIST',
          status: 'proposed',
        });
        setActionMessage('Remediation proposal generated: SCALE_CONTAINER_MEMORY (factor: 1.5x, simulation: true).');
        setActionBusy(false);
      }, 600);
      return;
    }

    try {
      const created = await apiClient.postProposal(detail.incident_id);
      setProposal(created);
      setActionMessage(`Remediation proposal created: ${created.action_id} (${created.status})`);
    } catch (err: unknown) {
      setActionMessage(`Failed to request proposal: ${(err as Error).message}`);
    } finally {
      setActionBusy(false);
    }
  };

  const handleApprove = async () => {
    if (!proposal) return;
    setActionBusy(true);
    setActionMessage('Submitting authorization to central policy engine (pending collector result)...');

    if (isFixtureMode) {
      // Simulate real lifecycle progression without instant local success
      setTimeout(() => {
        setProposal((prev) => (prev ? { ...prev, status: 'succeeded' } : null));
        setActionMessage('Simulated action executed by collector. Memory scaled factor 1.5x in test simulation.');
        setActionBusy(false);
      }, 900);
      return;
    }

    try {
      const updated = await apiClient.approveRemediation(proposal.action_id);
      setProposal(updated);
      setActionMessage(`Remediation status updated: ${updated.status}`);
    } catch (err: unknown) {
      setActionMessage(`Approval failed: ${(err as Error).message}`);
    } finally {
      setActionBusy(false);
    }
  };

  const handleRollback = async () => {
    if (!proposal) return;
    setActionBusy(true);
    setActionMessage('Requesting verified snapshot rollback from collector...');

    if (isFixtureMode) {
      setTimeout(() => {
        setProposal((prev) => (prev ? { ...prev, status: 'rolled_back' } : null));
        setActionMessage('Simulated action rolled back to pre-incident snapshot.');
        setActionBusy(false);
      }, 900);
      return;
    }

    try {
      const updated = await apiClient.rollbackRemediation(proposal.action_id);
      setProposal(updated);
      setActionMessage(`Rollback status updated: ${updated.status}`);
    } catch (err: unknown) {
      setActionMessage(`Rollback failed: ${(err as Error).message}`);
    } finally {
      setActionBusy(false);
    }
  };

  return (
    <div className="section-block incidents-section">
      <div className="section-header">
        <h2 className="section-title">Correlated Incidents & Remediation (AIOps)</h2>
        <span className="count-tag">{incidents.length} Active Incidents</span>
      </div>

      {listError && (
        <div className="alert-banner mb-3" role="alert">
          <strong>Incident Service Notice:</strong> {listError}
        </div>
      )}

      <div className="incidents-layout">
        {/* Incident List Sidebar */}
        <div className="incidents-sidebar">
          {incidents.length === 0 ? (
            <div className="empty-text">No open incidents detected.</div>
          ) : (
            incidents.map((inc) => (
              <button
                type="button"
                key={inc.incident_id}
                className={`incident-item ${selectedIncidentId === inc.incident_id ? 'selected' : ''}`}
                onClick={() => setSelectedIncidentId(inc.incident_id)}
              >
                <div className="item-row">
                  <span className={`severity-tag sev-${inc.severity}`}>
                    {inc.severity.toUpperCase()}
                  </span>
                  <span className="mono text-xs">{inc.incident_id}</span>
                </div>
                <div className="item-title">{inc.template_title}</div>
                <div className="item-meta">
                  <span>Score: {inc.evidence_score}</span>
                  <span>{new Date(inc.created_at_utc).toLocaleTimeString(undefined, { timeZone: 'UTC' })} UTC</span>
                </div>
              </button>
            ))
          )}
        </div>

        {/* Incident Detail */}
        <div className="incident-content">
          {detail ? (
            <div className="detail-card">
              <div className="detail-header">
                <div>
                  <span className={`severity-tag sev-${detail.severity}`}>{detail.severity.toUpperCase()}</span>
                  <h3 className="detail-title">{detail.template_title}</h3>
                  <div className="mono text-muted text-xs">
                    Incident ID: {detail.incident_id} &bull; Status: {detail.status.toUpperCase()}
                  </div>
                  {detail.alert_ids && detail.alert_ids.length > 0 && (
                    <div className="mono text-muted text-xs mt-1">
                      Correlated Alert IDs: {detail.alert_ids.join(', ')}
                    </div>
                  )}
                </div>

                {/* Heuristic Evidence Score Box */}
                <div className="evidence-score-box">
                  <div className="score-num">{detail.evidence_score} <span className="score-max">/ 100</span></div>
                  <div className="score-label">Heuristic Evidence Score</div>
                  {detail.score_method && (
                    <div className="mono text-xs text-muted">Method: {detail.score_method}</div>
                  )}
                  <div className="score-disclaimer">
                    Heuristic statistical correlation only. Calibrated confidence and causal certainty are deliberately omitted per policy.
                  </div>
                </div>
              </div>

              {/* Phase 5: Affected Pseudonymous Sources */}
              <div className="detail-section">
                <h4 className="detail-subhead">Affected Pseudonymous Sources ({detail.source_ids.length})</h4>
                <div className="source-badges-row">
                  {detail.source_ids.map((srcId) => (
                    <span key={srcId} className="pseudonym-badge mono">
                      <span className="privacy-dot" title="Pseudonymous identifier - no IP or hostname">●</span>
                      {srcId}
                    </span>
                  ))}
                </div>
                <div className="text-muted text-xs mt-1">
                  Pseudonyms are computed locally at the collector using tenant HMAC keys. Central SaaS never receives hostnames, IPs, or credentials.
                </div>
              </div>

              {/* Likely Root Mechanism */}
              <div className="detail-section">
                <h4 className="detail-subhead">Likely Root Mechanism (Statistical Synthesis)</h4>
                <p className="likely-cause-text">{detail.likely_cause}</p>
              </div>

              {/* Reasoning Chronology */}
              <div className="detail-section">
                <h4 className="detail-subhead">Reasoning Chronology</h4>
                <ol className="reasoning-list">
                  {detail.reasoning_steps.map((step, idx) => (
                    <li key={idx}>{step}</li>
                  ))}
                </ol>
              </div>

              {/* Contributing Signals (Statistical Deviations) */}
              <div className="detail-section">
                <h4 className="detail-subhead">Contributing Signals (Observed vs Baseline)</h4>
                <div className="table-responsive">
                  <table className="telemetry-table table-compact">
                    <thead>
                      <tr>
                        <th scope="col">Metric</th>
                        <th scope="col">Observed</th>
                        <th scope="col">Baseline Mean</th>
                        <th scope="col">Baseline Std</th>
                        <th scope="col">Comparison</th>
                        <th scope="col">Z-Score</th>
                        <th scope="col">Event Time (UTC)</th>
                        <th scope="col">Payload UUID</th>
                      </tr>
                    </thead>
                    <tbody>
                      {detail.contributing_signals.map((sig, i) => (
                        <tr key={i}>
                          <td className="mono font-semibold">{sig.metric}</td>
                          <td>{sig.observed.toFixed(1)}</td>
                          <td>{sig.baseline_mean !== null ? sig.baseline_mean.toFixed(1) : '—'}</td>
                          <td>{sig.baseline_std !== null ? sig.baseline_std.toFixed(1) : '—'}</td>
                          <td>{sig.baseline_mean === null ? '—' : (
                            <div className="signal-comparison">
                              <meter aria-label={`${sig.metric} observed`} value={sig.observed}
                                max={Math.max(sig.observed, sig.baseline_mean, 1)} />
                              <meter aria-label={`${sig.metric} baseline mean`} value={sig.baseline_mean}
                                max={Math.max(sig.observed, sig.baseline_mean, 1)} />
                            </div>
                          )}</td>
                          <td className="mono font-semibold text-alert">
                            {sig.z_score !== null ? `${sig.z_score > 0 ? '+' : ''}${sig.z_score.toFixed(2)}` : '—'}
                          </td>
                          <td className="mono text-xs">
                            {new Date(sig.event_time_utc).toISOString().replace('T', ' ').replace('Z', '')}
                          </td>
                          <td className="mono text-xs">
                            {onInspectPayload ? (
                              <button
                                type="button"
                                className="text-btn mono text-xs"
                                onClick={() => onInspectPayload(sig.payload_uuid)}
                                title="Inspect this payload in Egress Inspector"
                              >
                                {sig.payload_uuid} &rarr;
                              </button>
                            ) : (
                              <span className="text-muted">{sig.payload_uuid}</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Phase 6: Remediation Action Controls */}
              <div className="remediation-box">
                <div className="remediation-header">
                  <span className="sim-badge">SAFE SIMULATION PLAYBOOK</span>
                  <h4 className="remediation-title">
                    Autonomous Action: {proposal?.playbook || 'SCALE_CONTAINER_MEMORY'}
                  </h4>
                </div>

                <div className="sim-notice">
                  <strong>Simulation Invariant (simulation: true):</strong> Target action is hardcoded to safe container memory scaling in simulation. No production infrastructure is altered. Authorization is verified by central policy engine.
                </div>

                <p className="remediation-desc">
                  <strong>Recommended Action:</strong> {detail.recommended_action}
                </p>

                {proposal ? (
                  <div className="action-status-card">
                    <div className="action-meta-grid">
                      <div>
                        <span className="meta-label">Action ID:</span>
                        <span className="mono text-xs">{proposal.action_id}</span>
                      </div>
                      <div>
                        <span className="meta-label">Target Source:</span>
                        <span className="mono text-xs">{proposal.target_source_id}</span>
                      </div>
                      <div>
                        <span className="meta-label">Scale Factor:</span>
                        <span className="mono text-xs">{proposal.factor}x</span>
                      </div>
                      <div>
                        <span className="meta-label">Policy Verdict:</span>
                        <span className="tag-valid text-xs">{proposal.policy_verdict}</span>
                      </div>
                    </div>

                    <div className="action-status-row mt-3">
                      <div className="status-indicator">
                        Current Lifecycle State:{' '}
                        <span className="mono font-semibold state-badge">{proposal.status.toUpperCase()}</span>
                      </div>

                      <div className="action-buttons-group">
                        <button
                          type="button"
                          className="btn-action-approve"
                          onClick={handleApprove}
                          disabled={
                            actionBusy ||
                            proposal.status !== 'proposed'
                          }
                          title={proposal.status !== 'proposed' ? `Cannot approve in '${proposal.status}' state` : 'Approve simulation action'}
                        >
                          {proposal.status === 'succeeded'
                            ? 'Action Applied'
                            : proposal.status === 'executing' || proposal.status === 'approved'
                            ? 'Awaiting Collector...'
                            : 'Approve Remediation'}
                        </button>

                        <button
                          type="button"
                          className="btn-action-rollback"
                          onClick={handleRollback}
                          disabled={
                            actionBusy ||
                            proposal.status !== 'succeeded'
                          }
                          title="Rollback to pre-incident snapshot if remediation fails or is revoked"
                        >
                          {proposal.status === 'rollback_pending'
                            ? 'Rolling back...'
                            : proposal.status === 'rolled_back'
                            ? 'Rolled Back'
                            : 'Rollback to Snapshot'}
                        </button>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="no-proposal-box">
                    <span className="text-muted text-sm">No action proposal requested for this incident yet.</span>
                    <button
                      type="button"
                      className="btn-request-proposal"
                      onClick={handleRequestProposal}
                      disabled={actionBusy || (!isFixtureMode && !detail.remediation_eligible)}
                    >
                      Request Remediation Proposal
                    </button>
                  </div>
                )}

                {actionMessage && (
                  <div className="action-log-message mono" role="status" aria-live="polite">
                    {actionMessage}
                  </div>
                )}

                {/* Remediation Audit Trail */}
                {auditTrail.length > 0 && (
                  <div className="audit-trail-section mt-4">
                    <h5 className="audit-trail-title">Remediation Audit Log</h5>
                    <div className="table-responsive">
                      <table className="telemetry-table table-compact">
                        <thead>
                          <tr>
                            <th scope="col">Action ID</th>
                            <th scope="col">Incident</th>
                            <th scope="col">Target</th>
                            <th scope="col">Playbook</th>
                            <th scope="col">Status</th>
                            <th scope="col">Reason Code</th>
                            <th scope="col">Actor</th>
                            <th scope="col">Time (UTC)</th>
                          </tr>
                        </thead>
                        <tbody>
                          {auditTrail.filter((act) => act.incident_id === detail.incident_id).map((act) => (
                            <tr key={act.audit_id}>
                              <td className="mono text-xs">{act.action_id}</td>
                              <td className="mono text-xs">{act.incident_id}</td>
                              <td className="mono text-xs">{act.target_source_id}</td>
                              <td className="mono text-xs">{act.playbook}</td>
                              <td>
                                <span className="mono text-xs font-semibold">{act.status.toUpperCase()}</span>
                              </td>
                              <td className="mono text-xs text-muted">{act.reason_code}</td>
                              <td className="mono text-xs">{act.actor}</td>
                              <td className="mono text-xs">{act.occurred_at}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="empty-text">Select an incident to view root evidence and remediation options.</div>
          )}
        </div>
      </div>
    </div>
  );
};
