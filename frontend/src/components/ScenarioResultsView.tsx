import React, { useState, useEffect } from 'react';
import type { ScenarioResult } from '../types/contracts';
import { apiClient } from '../api/client';
import { MOCK_SCENARIO_RESULTS } from '../fixtures/metadataFixtures';

interface ScenarioResultsViewProps {
  isFixtureMode: boolean;
}

const SCENARIO_NAMES: Record<number, string> = {
  1: 'Raw Event Conformance & Adapter Parsing',
  2: 'Zero-Egress Secret Redaction & Body SHA-256 Digest',
  3: 'Resilient Outage Buffering & Outbox Drain',
  4: 'Local Failed-Login Risk Analyzer',
  5: 'Network Degradation & Sub-15s Alerting',
  6: 'Statistical Baseline Anomaly Detection',
  7: 'Alert Storm Correlation & Topology Grouping',
  8: 'Deduplication & Temporal UTC Ordering',
};

export const ScenarioResultsView: React.FC<ScenarioResultsViewProps> = ({ isFixtureMode }) => {
  const [results, setResults] = useState<ScenarioResult[]>(
    isFixtureMode ? MOCK_SCENARIO_RESULTS : [],
  );
  const [loading, setLoading] = useState<boolean>(false);

  useEffect(() => {
    if (isFixtureMode) {
      setResults(MOCK_SCENARIO_RESULTS);
      return;
    }

    let active = true;
    const fetchResults = async () => {
      setLoading(true);
      try {
        const res = await apiClient.getScenarioResults();
        if (active) setResults(res);
      } catch {
        if (active) setResults([]);
      } finally {
        if (active) setLoading(false);
      }
    };

    fetchResults();
    return () => {
      active = false;
    };
  }, [isFixtureMode]);

  return (
    <div className="section-block scenarios-section">
      <div className="section-header">
        <h2 className="section-title">Hackathon Scenario Verification Results</h2>
        <span className="count-tag">8 Verification Scenarios</span>
      </div>

      <div className="scenario-info-banner">
        <strong>Execution Notice:</strong> Chaos injection and scenario runners execute locally on Member 3's isolated test environment.
        To trigger chaos injection or view raw collector loopback logs, open{' '}
        <a href="http://localhost:9001" target="_blank" rel="noreferrer" className="external-link">
          http://localhost:9001
        </a>{' '}
        in a separate browser window. This SaaS view displays only verified central summary results.
      </div>

      {loading && results.length === 0 ? (
        <div className="loading-text">Loading scenario verification status...</div>
      ) : results.length === 0 ? (
        <div className="empty-text">No scenario verification results reported yet. Run tests via local harness.</div>
      ) : (
        <div className="scenarios-grid">
          {results.map((scen) => (
            <div key={scen.scenario_id} className="scenario-card">
              <div className="scenario-card-header">
                <span className="scenario-number">Scenario {scen.scenario_id}</span>
                <span className={`status-tag ${scen.status === 'passed' ? 'tag-valid' : scen.status === 'failed' ? 'tag-alert' : 'tag-warn'}`}>
                  {scen.status.toUpperCase()}
                </span>
              </div>

              <h4 className="scenario-title">
                {SCENARIO_NAMES[scen.scenario_id] || `Scenario ${scen.scenario_id}`}
              </h4>

              <div className="scenario-meta mono text-xs">
                <div>Run ID: {scen.run_id}</div>
                <div>Completed: {new Date(scen.finished_at_utc).toLocaleTimeString()} UTC</div>
                {scen.reason_code && <div>Verdict: {scen.reason_code}</div>}
              </div>

              <div className="checks-list">
                <div className="checks-title">Assertion Checks:</div>
                {Object.entries(scen.checks).map(([checkKey, val]) => (
                  <div key={checkKey} className="check-row">
                    <span className="check-key">{checkKey}</span>
                    <span className={`check-val mono ${typeof val === 'boolean' ? (val ? 'text-valid' : 'text-alert') : ''}`}>
                      {String(val)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
