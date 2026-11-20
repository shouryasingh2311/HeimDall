import { useEffect, useState } from 'react';
import { apiClient } from '../api/client';
import type { BenchmarkSummary } from '../types/contracts';

export function BenchmarkPanel() {
  const [data, setData] = useState<BenchmarkSummary | null>(null);
  const [unavailable, setUnavailable] = useState(false);
  useEffect(() => {
    let active = true;
    const refresh = async () => {
      try {
        const result = await apiClient.getBenchmarks();
        if (active) {
          setData(result);
          setUnavailable(false);
        }
      } catch {
        if (active) setUnavailable(true);
      }
    };
    void refresh();
    const timer = window.setInterval(refresh, 5000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);

  return (
    <section className="section-block" aria-labelledby="benchmark-title">
      <h2 id="benchmark-title" className="section-title">Measured render timing</h2>
      {unavailable ? <p>Timing data is unavailable.</p> : data ? (
        <>
          <p>{data.window_seconds / 60}-minute window for this dashboard session. {data.clock_uncertainty}</p>
          <div className="table-responsive">
            <table className="telemetry-table">
              <thead>
                <tr><th>Cohort</th><th>Samples</th><th>Missing</th><th>Clock flagged</th><th>p95</th></tr>
              </thead>
              <tbody>
                {(['live', 'replay_or_delayed', 'all'] as const).map((key) => {
                  const cohort = data[key];
                  const label = { live: 'Live', replay_or_delayed: 'Replay or delayed', all: 'All' }[key];
                  return (
                    <tr key={key}><td>{label}</td><td>{cohort.samples} / {cohort.eligible}</td>
                      <td>{cohort.missing}</td><td>{cohort.clock_flagged}</td>
                      <td>{cohort.p95_ms === null ? '—' : `${(cohort.p95_ms / 1000).toFixed(2)} s`}</td></tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p>{data.offline.length ? `Latest offline detection: ${(data.offline[0].delay_ms / 1000).toFixed(2)} s.` : 'No offline detection recorded in this window.'}</p>
          <p>{data.alert_delay_ms === null ? 'Alert timing pending Phase 5.' : `Alert delay: ${(data.alert_delay_ms / 1000).toFixed(2)} s.`}</p>
        </>
      ) : <p>Loading timing data…</p>}
    </section>
  );
}
