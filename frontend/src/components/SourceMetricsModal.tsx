import React, { useState, useEffect } from 'react';
import type { FleetSource, PayloadDetail } from '../types/contracts';
import { apiClient } from '../api/client';
import { MOCK_SOURCE_METRICS_STORE } from '../fixtures/metadataFixtures';

interface SourceMetricsModalProps {
  source: FleetSource | null;
  onClose: () => void;
  isFixtureMode: boolean;
  onInspectPayload?: (uuid: string) => void;
}

export const SourceMetricsModal: React.FC<SourceMetricsModalProps> = ({
  source,
  onClose,
  isFixtureMode,
  onInspectPayload,
}) => {
  const [history, setHistory] = useState<PayloadDetail[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!source) return;

    // Keyboard listener for Escape key to close modal
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);

    if (isFixtureMode) {
      const mockPoints = MOCK_SOURCE_METRICS_STORE[source.source_id] || [];
      // Strictly sort by event_time_utc ascending per Phase 4 / CONTRACTS.md
      const sorted = [...mockPoints].sort(
        (a, b) => new Date(a.event_time_utc).getTime() - new Date(b.event_time_utc).getTime(),
      );
      setHistory(sorted);
      setLoading(false);
      return () => window.removeEventListener('keydown', handleKeyDown);
    }

    let active = true;
    const fetchHistory = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await apiClient.getSourceMetrics(source.source_id);
        if (active) {
          // Strictly sort by event_time_utc ascending per Phase 4 / CONTRACTS.md
          const sorted = [...res.items].sort(
            (a, b) => new Date(a.event_time_utc).getTime() - new Date(b.event_time_utc).getTime(),
          );
          setHistory(sorted);
        }
      } catch (err: unknown) {
        if (active) {
          setError((err as Error).message || 'Failed to fetch historical source metrics');
        }
      } finally {
        if (active) setLoading(false);
      }
    };

    fetchHistory();
    return () => {
      active = false;
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [source, isFixtureMode, onClose]);

  if (!source) return null;

  // Pure SVG sparkline generator (0..100% scale)
  const renderSparkline = (
    values: number[],
    minVal = 0,
    maxVal = 100,
    strokeColor = '#3b82f6',
  ) => {
    if (values.length < 2) {
      return <div className="text-xs text-muted">Insufficient historical points</div>;
    }
    const width = 280;
    const height = 60;
    const padding = 6;
    const plotWidth = width - padding * 2;
    const plotHeight = height - padding * 2;

    const range = maxVal - minVal || 1;
    const points = values.map((val, idx) => {
      const x = padding + (idx / (values.length - 1)) * plotWidth;
      const normalized = Math.max(0, Math.min(1, (val - minVal) / range));
      const y = height - padding - normalized * plotHeight;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    });

    const pathData = `M ${points.join(' L ')}`;

    return (
      <svg className="sparkline-svg" width={width} height={height} aria-hidden="true">
        <path d={pathData} fill="none" stroke={strokeColor} strokeWidth="2" strokeLinecap="round" />
        {points.map((pt, i) => {
          const [cx, cy] = pt.split(',');
          return <circle key={i} cx={cx} cy={cy} r="3" fill={strokeColor} />;
        })}
      </svg>
    );
  };

  const cpuPoints = history.map((h) => h.metrics?.cpu_pct ?? 0);
  const memPoints = history.map((h) => h.metrics?.memory_pct ?? 0);
  const latPoints = history.map((h) => h.metrics?.latency_ms ?? 0);
  const maxLat = Math.max(100, ...latPoints);

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="source-modal-title">
      <div className="modal-content modal-large">
        <div className="modal-header">
          <div>
            <span className="count-tag font-semibold">SOURCE TELEMETRY ENGINE</span>
            <h2 id="source-modal-title" className="modal-title mono">
              {source.source_id}
            </h2>
            <div className="text-xs text-muted">Collector: {source.collector_id}</div>
          </div>
          <button type="button" className="modal-close-btn" onClick={onClose} aria-label="Close dialog">
            &times;
          </button>
        </div>

        {/* Phase 4 Sparkline Trends */}
        <div className="sparklines-grid">
          <div className="sparkline-card">
            <div className="sparkline-meta">
              <span className="sparkline-title">CPU Utilization</span>
              <span className="sparkline-latest mono font-semibold">
                {source.metrics.cpu_pct !== null ? `${source.metrics.cpu_pct.toFixed(1)}%` : '—'}
              </span>
            </div>
            {renderSparkline(cpuPoints, 0, 100, '#10b981')}
            <span className="text-xs text-muted">Scale: 0% - 100%</span>
          </div>

          <div className="sparkline-card">
            <div className="sparkline-meta">
              <span className="sparkline-title">Memory Allocation</span>
              <span className="sparkline-latest mono font-semibold">
                {source.metrics.memory_pct !== null ? `${source.metrics.memory_pct.toFixed(1)}%` : '—'}
              </span>
            </div>
            {renderSparkline(memPoints, 0, 100, '#3b82f6')}
            <span className="text-xs text-muted">Scale: 0% - 100%</span>
          </div>

          <div className="sparkline-card">
            <div className="sparkline-meta">
              <span className="sparkline-title">Request Latency</span>
              <span className="sparkline-latest mono font-semibold">
                {source.metrics.latency_ms !== null ? `${source.metrics.latency_ms.toFixed(1)} ms` : '—'}
              </span>
            </div>
            {renderSparkline(latPoints, 0, maxLat, '#f59e0b')}
            <span className="text-xs text-muted">Scale: 0ms - {maxLat.toFixed(0)}ms</span>
          </div>
        </div>

        {error && (
          <div className="error-callout" role="alert">
            <div className="error-title">Historical Telemetry Unavailable</div>
            <div className="error-detail">{error}</div>
          </div>
        )}

        {/* Chronological Event-Time Sorted Table */}
        <div className="historical-table-section">
          <div className="table-header-row">
            <h4 className="section-title">Temporal Event Sequence (Strict Event-Time UTC)</h4>
            <span className="count-tag">{history.length} Data Points</span>
          </div>

          {loading ? (
            <div className="loading-text">Loading historical data points...</div>
          ) : history.length === 0 ? (
            <div className="empty-text">No historical metrics received for this source yet.</div>
          ) : (
            <div className="table-responsive">
              <table className="telemetry-table table-compact">
                <thead>
                  <tr>
                    <th>Event Time (UTC)</th>
                    <th>CPU %</th>
                    <th>Memory %</th>
                    <th>Disk %</th>
                    <th>Latency</th>
                    <th>Loss</th>
                    <th>Receipt Digest</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map((pt) => (
                    <tr key={pt.payload_uuid}>
                      <td className="mono text-xs">{new Date(pt.event_time_utc).toLocaleTimeString()} UTC</td>
                      <td>{pt.metrics?.cpu_pct !== null ? `${pt.metrics?.cpu_pct.toFixed(1)}%` : '—'}</td>
                      <td>{pt.metrics?.memory_pct !== null ? `${pt.metrics?.memory_pct.toFixed(1)}%` : '—'}</td>
                      <td>{pt.metrics?.disk_used_pct !== null ? `${pt.metrics?.disk_used_pct.toFixed(1)}%` : '—'}</td>
                      <td>{pt.metrics?.latency_ms !== null ? `${pt.metrics?.latency_ms.toFixed(1)} ms` : '—'}</td>
                      <td>{pt.metrics?.packet_loss_pct !== null ? `${pt.metrics?.packet_loss_pct.toFixed(1)}%` : '—'}</td>
                      <td className="mono text-xs text-muted" title={pt.body_sha256}>
                        {pt.body_sha256.substring(0, 12)}...
                      </td>
                      <td>
                        {onInspectPayload && (
                          <button
                            type="button"
                            className="text-btn text-xs font-semibold"
                            onClick={() => {
                              onInspectPayload(pt.payload_uuid);
                              onClose();
                            }}
                          >
                            Inspect Payload &rarr;
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="modal-footer">
          <button type="button" className="action-btn" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
