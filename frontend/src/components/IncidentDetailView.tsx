import React, { useState, useEffect } from 'react';
import type { IncidentSummary, IncidentDetail, ActionProposal } from '../types/contracts';
import { apiClient } from '../api/client';
import {
  MOCK_INCIDENTS_SUMMARY,
  MOCK_INCIDENT_DETAIL,
  MOCK_ACTION_PROPOSAL,
} from '../fixtures/metadataFixtures';

interface IncidentDetailViewProps {
  isFixtureMode: boolean;
  onInspectPayload?: (uuid: string) => void;
}

export const IncidentDetailView: React.FC<IncidentDetailViewProps> = ({ isFixtureMode, onInspectPayload }) => {
  const [incidents, setIncidents] = useState<IncidentSummary[]>(
    isFixtureMode ? MOCK_INCIDENTS_SUMMARY : [],
  );
  const [selectedIncidentId, setSelectedIncidentId] = useState<string | null>(
    isFixtureMode ? MOCK_INCIDENTS_SUMMARY[0]?.incident_id || null : null,
  );
  const [detail, setDetail] = useState<IncidentDetail | null>(
    isFixtureMode ? MOCK_INCIDENT_DETAIL : null,
  );
  const [proposal, setProposal] = useState<ActionProposal | null>(
    isFixtureMode ? MOCK_ACTION_PROPOSAL : null,
  );
  const [actionBusy, setActionBusy] = useState<boolean>(false);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  useEffect(() => {
    if (isFixtureMode) {
      setIncidents(MOCK_INCIDENTS_SUMMARY);
      setSelectedIncidentId(MOCK_INCIDENTS_SUMMARY[0]?.incident_id || null);
      setDetail(MOCK_INCIDENT_DETAIL);
      setProposal(MOCK_ACTION_PROPOSAL);
      return;
    }

    let active = true;
    const fetchIncidents = async () => {
      try {
        const list = await apiClient.getIncidents();
        if (active) {
          setIncidents(list);
          if (list.length > 0 && !selectedIncidentId) {
            setSelectedIncidentId(list[0].incident_id);
          }
        }
      } catch {
        if (active) setIncidents([]);
      }
    };

    fetchIncidents();
    return () => {
      active = false;
    };
  }, [isFixtureMode, selectedIncidentId]);

  useEffect(() => {
    if (!selectedIncidentId || isFixtureMode) return;

    let active = true;
    const fetchDetail = async () => {
      try {
        const d = await apiClient.getIncident(selectedIncidentId);
        if (active) {
          setDetail(d);
          if (d.proposal_status !== 'none') {
            setProposal({
              action_id: `act-${d.incident_id}`,
              incident_id: d.incident_id,
              target_source_id: d.source_ids[0] || 'src-unknown',
              playbook: 'SCALE_CONTAINER_MEMORY',
              factor: 1.5,
              simulation: true,
              policy_verdict: 'APPROVED_BY_POLICY',
              reason_code: 'TARGET_IN_SIMULATION_ALLOWLIST',
              status: d.proposal_status as ActionProposal['status'],
            });
          }
        }
      } catch {
        if (active) setDetail(null);
      }
    };

    fetchDetail();
    return () => {
      active = false;
    };
  }, [selectedIncidentId, isFixtureMode]);

  const handleApprove = async () => {
    if (!proposal) return;
    setActionBusy(true);
    setActionMessage('Submitting authorization to central policy engine...');

    if (isFixtureMode) {
      // Simulate real lifecycle progression without instant local success
      setTimeout(() => {
        setProposal((prev) => (prev ? { ...prev, status: 'succeeded' } : null));
        setActionMessage('Simulated action executed successfully. Memory scaled factor 1.5x in simulation.');
        setActionBusy(false);
      }, 800);
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
    setActionMessage('Requesting verified snapshot rollback...');

    if (isFixtureMode) {
      setTimeout(() => {
        setProposal((prev) => (prev ? { ...prev, status: 'rolled_back' } : null));
        setActionMessage('Simulated action rolled back to pre-incident snapshot.');
        setActionBusy(false);
      }, 800);
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

      <div className="incidents-layout">
        {/* Incident List */}
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
                  <span>{new Date(inc.created_at_utc).toLocaleTimeString()} UTC</span>
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
                  <div className="mono text-muted text-xs">Incident ID: {detail.incident_id}</div>
                </div>

                <div className="evidence-score-box">
                  <div className="score-num">{detail.evidence_score}</div>
                  <div className="score-label">Heuristic Evidence Score</div>
                  <div className="score-disclaimer">Statistical correlation only — no causal certainty claimed</div>
                </div>
              </div>

              <div className="detail-section">
                <h4 className="detail-subhead">Likely Root Mechanism</h4>
                <p className="likely-cause-text">{detail.likely_cause}</p>
              </div>

              <div className="detail-section">
                <h4 className="detail-subhead">Reasoning Chronology</h4>
                <ol className="reasoning-list">
                  {detail.reasoning_steps.map((step, idx) => (
                    <li key={idx}>{step}</li>
                  ))}
                </ol>
              </div>

              <div className="detail-section">
                <h4 className="detail-subhead">Contributing Signals (Statistical Deviations)</h4>
                <div className="table-responsive">
                  <table className="telemetry-table table-compact">
                    <thead>
                      <tr>
                        <th>Metric</th>
                        <th>Observed</th>
                        <th>Baseline Mean</th>
                        <th>Baseline Std</th>
                        <th>Z-Score</th>
                        <th>Payload UUID</th>
                      </tr>
                    </thead>
                    <tbody>
                      {detail.contributing_signals.map((sig, i) => (
                        <tr key={i}>
                          <td className="mono font-semibold">{sig.metric}</td>
                          <td>{sig.observed.toFixed(1)}</td>
                          <td>{sig.baseline_mean !== null ? sig.baseline_mean.toFixed(1) : '—'}</td>
                          <td>{sig.baseline_std !== null ? sig.baseline_std.toFixed(1) : '—'}</td>
                          <td className="mono font-semibold text-alert">
                            {sig.z_score !== null ? `+${sig.z_score.toFixed(2)}` : '—'}
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

              {/* Remediation Action Controls (Phase 6) */}
              <div className="remediation-box">
                <div className="remediation-header">
                  <span className="sim-badge">SAFE SIMULATION PLAYBOOK</span>
                  <h4 className="remediation-title">Autonomous Action Proposal: {proposal?.playbook || 'SCALE_CONTAINER_MEMORY'}</h4>
                </div>

                <p className="remediation-desc">
                  <strong>Recommended Action:</strong> {detail.recommended_action}
                </p>

                {proposal && (
                  <div className="action-status-row">
                    <div className="status-indicator">
                      Current State: <span className="mono font-semibold">{proposal.status.toUpperCase()}</span>
                    </div>
                    <div className="action-buttons-group">
                      <button
                        type="button"
                        className="btn-action-approve"
                        onClick={handleApprove}
                        disabled={actionBusy || proposal.status === 'succeeded' || proposal.status === 'executing'}
                      >
                        {proposal.status === 'succeeded' ? 'Action Applied' : 'Approve Remediation'}
                      </button>

                      <button
                        type="button"
                        className="btn-action-rollback"
                        onClick={handleRollback}
                        disabled={actionBusy || proposal.status !== 'succeeded'}
                        title="Rollback to snapshot if remediation fails or is rejected"
                      >
                        Rollback to Snapshot
                      </button>
                    </div>
                  </div>
                )}

                {actionMessage && (
                  <div className="action-log-message mono">{actionMessage}</div>
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
