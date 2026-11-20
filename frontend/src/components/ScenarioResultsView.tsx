import React, { useState, useEffect } from 'react';
import type { ScenarioResult } from '../types/contracts';
import { apiClient } from '../api/client';
import { MOCK_SCENARIO_RESULTS } from '../fixtures/metadataFixtures';

interface ScenarioResultsViewProps {
  isFixtureMode: boolean;
  onInspectPayload?: (uuid: string) => void;
  onSelectIncident?: (incidentId: string) => void;
}

const SCENARIO_NAMES: Record<number, string> = {
  1: 'Raw Event Conformance & Adapter Parsing (V01)',
  2: 'Zero-Egress Secret Redaction & Body SHA-256 Digest (V02, V03)',
  3: 'Resilient Outage Buffering & Outbox Drain (V04)',
  4: 'Local Failed-Login Risk Analyzer (V05)',
  5: 'Network Degradation & Sub-15s Alerting (V06)',
  6: 'Statistical Baseline Anomaly Detection (V07)',
  7: 'Alert Storm Correlation & Topology Grouping (V08)',
  8: 'Deduplication & Temporal UTC Ordering (V09)',
};

export const ScenarioResultsView: React.FC<ScenarioResultsViewProps> = ({
  isFixtureMode,
  onInspectPayload,
  onSelectIncident,
}) => {
  const [results, setResults] = useState<ScenarioResult[]>(
    isFixtureMode ? MOCK_SCENARIO_RESULTS : [],
  );
  const [loading, setLoading] = useState<boolean>(false);
  const [fetchError, setFetchError] = useState<string | null>(null);

  const fetchResults = async () => {
    if (isFixtureMode) {
      setResults(MOCK_SCENARIO_RESULTS);
      setFetchError(null);
      return;
    }

    setLoading(true);
    setFetchError(null);
    try {
      const res = await apiClient.getScenarioResults();
      setResults(res);
    } catch (err: unknown) {
      setResults([]);
      setFetchError((err as Error).message || 'Failed to connect to /api/v1/scenario-results');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchResults();
  }, [isFixtureMode]);

  // Aggregate status metrics
  const passedCount = results.filter((r) => r.status === 'passed').length;
  const failedCount = results.filter((r) => r.status === 'failed').length;
  const runningCount = results.filter((r) => r.status === 'running').length;
  const blockedCount = results.filter((r) => r.status === 'blocked').length;

  return (
    <div className="section-block scenarios-section">
      <div className="section-header">
        <h2 className="section-title">Hackathon Scenario Verification (1–8)</h2>
        <div className="header-actions">
          <span className="count-tag">8 Verification Scenarios</span>
          <button
            type="button"
            className="action-btn text-xs"
            onClick={fetchResults}
            disabled={loading}
          >
            {loading ? 'Refreshing...' : 'Refresh Results'}
          </button>
        </div>
      </div>

      {/* Local Runner Isolation Notice */}
      <div className="scenario-info-banner">
        <strong>Isolated Verification Architecture (Phase 7):</strong> Chaos injection, adapter parsing, and scenario drivers run locally in Member 3&apos;s runner environment.
        To trigger chaos injection or view raw collector loopback tests, open{' '}
        <a href="http://localhost:9001/audit" target="_blank" rel="noreferrer" className="external-link">
          http://localhost:9001/audit
        </a>{' '}
        in a separate browser window. This central SaaS view displays only verified summary metrics and approved cryptographic digests.
      </div>

      {/* Aggregate Scoreboard */}
      <div className="scenario-scoreboard">
        <div className="score-stat">
          <span className="stat-label">Total Scenarios:</span>
          <span className="stat-val mono">8</span>
        </div>
        <div className="score-stat">
          <span className="stat-label">Verified Passed:</span>
          <span className="stat-val mono text-valid">{passedCount} / 8</span>
        </div>
        <div className="score-stat">
          <span className="stat-label">Running:</span>
          <span className="stat-val mono">{runningCount}</span>
        </div>
        <div className="score-stat">
          <span className="stat-label">Failed:</span>
          <span className="stat-val mono text-alert">{failedCount}</span>
        </div>
        <div className="score-stat">
          <span className="stat-label">Blocked:</span>
          <span className="stat-val mono text-warn">{blockedCount}</span>
        </div>
      </div>

      {/* Honest Error State */}
      {fetchError && (
        <div className="alert-banner mb-3" role="alert">
          <strong>Scenario Summary Service Notice:</strong> {fetchError}.
          Scenario runners and local raw test logs remain isolated on Member 3&apos;s local test harness.
        </div>
      )}

      {loading && results.length === 0 ? (
        <div className="loading-text">Loading scenario verification status from SaaS...</div>
      ) : results.length === 0 && !fetchError ? (
        <div className="empty-text">No scenario verification results reported yet. Run tests via local test harness.</div>
      ) : (
        <div className="scenarios-grid">
          {results.map((scen) => (
            <div key={scen.scenario_id} className="scenario-card">
              <div className="scenario-card-header">
                <span className="scenario-number">Scenario {scen.scenario_id}</span>
                <span
                  className={`status-tag ${
                    scen.status === 'passed'
                      ? 'tag-valid'
                      : scen.status === 'failed'
                      ? 'tag-alert'
                      : 'tag-warn'
                  }`}
                >
                  {scen.status.toUpperCase()}
                </span>
              </div>

              <h4 className="scenario-title">
                {SCENARIO_NAMES[scen.scenario_id] || `Scenario ${scen.scenario_id}`}
              </h4>

              <div className="scenario-meta mono text-xs">
                <div>Run ID: {scen.run_id}</div>
                <div>Completed: {new Date(scen.finished_at_utc).toLocaleTimeString()} UTC</div>
                {scen.reason_code && (
                  <div className="verdict-line">Verdict: <strong>{scen.reason_code}</strong></div>
                )}
                {scen.duplicate_count > 0 && (
                  <div>Deduplicated: {scen.duplicate_count} events</div>
                )}
              </div>

              {/* Assertion Checks */}
              <div className="checks-list">
                <div className="checks-title">Assertion Checks:</div>
                {Object.entries(scen.checks).map(([checkKey, val]) => (
                  <div key={checkKey} className="check-row">
                    <span className="check-key">{checkKey}</span>
                    <span
                      className={`check-val mono ${
                        typeof val === 'boolean'
                          ? val
                            ? 'text-valid'
                            : 'text-alert'
                          : ''
                      }`}
                    >
                      {String(val)}
                    </span>
                  </div>
                ))}
              </div>

              {/* Contributing Payload UUIDs */}
              {scen.payload_uuids && scen.payload_uuids.length > 0 && (
                <div className="scenario-links-row">
                  <span className="links-label">Egress Payloads:</span>
                  <div className="badges-flow">
                    {scen.payload_uuids.map((uuid) => (
                      <button
                        key={uuid}
                        type="button"
                        className="chip-btn text-xs mono"
                        onClick={() => onInspectPayload && onInspectPayload(uuid)}
                        title="Inspect payload in Egress Inspector"
                      >
                        {uuid} &rarr;
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Contributing Incident IDs */}
              {scen.incident_ids && scen.incident_ids.length > 0 && (
                <div className="scenario-links-row">
                  <span className="links-label">Triggered Incidents:</span>
                  <div className="badges-flow">
                    {scen.incident_ids.map((incId) => (
                      <button
                        key={incId}
                        type="button"
                        className="chip-btn text-xs mono"
                        onClick={() => onSelectIncident && onSelectIncident(incId)}
                        title="View incident details"
                      >
                        {incId} &rarr;
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
