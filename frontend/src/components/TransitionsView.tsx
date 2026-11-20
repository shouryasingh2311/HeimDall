import React, { useState, useEffect } from 'react';
import type { StateTransition } from '../types/contracts';
import { apiClient } from '../api/client';
import { MOCK_TRANSITIONS_RESPONSE } from '../fixtures/metadataFixtures';

interface TransitionsViewProps {
  isFixtureMode: boolean;
}

export const TransitionsView: React.FC<TransitionsViewProps> = ({ isFixtureMode }) => {
  const [transitions, setTransitions] = useState<StateTransition[]>(
    isFixtureMode ? MOCK_TRANSITIONS_RESPONSE.items : [],
  );
  const [loading, setLoading] = useState<boolean>(false);
  const [unavailable, setUnavailable] = useState(false);

  useEffect(() => {
    if (isFixtureMode) {
      setTransitions(MOCK_TRANSITIONS_RESPONSE.items);
      setUnavailable(false);
      return;
    }

    let active = true;
    let timer: number | undefined;
    setLoading(true);
    const fetchTransitions = async () => {
      try {
        const res = await apiClient.getTransitions();
        if (active) {
          setTransitions(res.items);
          setUnavailable(false);
        }
      } catch {
        if (active) setUnavailable(true);
      } finally {
        if (active) {
          setLoading(false);
          timer = window.setTimeout(fetchTransitions, 2000);
        }
      }
    };

    fetchTransitions();
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [isFixtureMode]);

  return (
    <div className="section-block transitions-section">
      <div className="section-header">
        <h2 className="section-title">Health transitions</h2>
        <span className="count-tag">{transitions.length} recorded</span>
      </div>

      {unavailable ? (
        <div className="empty-text">Transition history is unavailable.</div>
      ) : loading && transitions.length === 0 ? (
        <div className="loading-text">Loading state transition history...</div>
      ) : transitions.length === 0 ? (
        <div className="empty-text">No state transitions recorded in this observation window.</div>
      ) : (
        <div className="table-responsive">
          <table className="telemetry-table">
            <thead>
              <tr>
                <th>Entity ID</th>
                <th>Type</th>
                <th>Transition</th>
                <th>Reason Codes</th>
                <th>Timestamp (UTC)</th>
              </tr>
            </thead>
            <tbody>
              {transitions.map((tr) => (
                <tr key={tr.transition_id}>
                  <td className="mono font-semibold">{tr.entity_id}</td>
                  <td className="text-sm">{tr.entity_type}</td>
                  <td>
                    <span className="transition-flow">
                      <span className="state-from">{tr.from_state}</span>
                      <span className="arrow-icon"> &rarr; </span>
                      <span className={`state-to font-semibold ${tr.to_state === 'Poor' ? 'text-alert' : ''}`}>
                        {tr.to_state}
                      </span>
                    </span>
                  </td>
                  <td>
                    <div className="reason-chips">
                      {tr.reason_codes.map((rc, i) => (
                        <span key={i} className="chip">{rc}</span>
                      ))}
                    </div>
                  </td>
                  <td className="mono text-muted text-sm">
                    {new Date(tr.timestamp_utc).toISOString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
