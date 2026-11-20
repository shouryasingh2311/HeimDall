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
  const sourceId = source?.source_id;
  const latestUuid = source?.payload_uuid;

  useEffect(() => {
    if (!sourceId) return;

    // Keyboard listener for Escape key to close modal
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);

    if (isFixtureMode) {
      setError(null);
      const mockPoints = MOCK_SOURCE_METRICS_STORE[sourceId] || [];
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
        const res = await apiClient.getSourceMetrics(sourceId, 50, undefined, true);
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
  }, [sourceId, latestUuid, isFixtureMode, onClose]);

  if (!source) return null;

  // Pure SVG sparkline generator (0..100% scale)
  const renderSparkline = (
    values: (number | null)[],
    minVal = 0,
    maxVal = 100,
    strokeColor = '#3b82f6',
  ) => {
    if (values.filter((value) => value !== null).length < 2) {
      return <div className="text-xs text-muted">Insufficient historical points</div>;
    }
    const width = 280;
    const height = 60;
    const padding = 6;
    const plotWidth = width - padding * 2;
    const plotHeight = height - padding * 2;

    const range = maxVal - minVal || 1;
    const times = history.map((point) => Date.parse(point.event_time_utc));
    const duration = (times.at(-1) ?? times[0]) - times[0];
    const points = values.map((val, idx) => {
      if (val === null) return null;
      const fraction = duration > 0 ? (times[idx] - times[0]) / duration : idx / (values.length - 1);
      const x = padding + fraction * plotWidth;
      const normalized = Math.max(0, Math.min(1, (val - minVal) / range));
      const y = height - padding - normalized * plotHeight;
      return [x, y];
    });

    const pathData = points.map((point, idx) => (
      point ? `${points[idx - 1] ? 'L' : 'M'} ${point.join(',')}` : ''
    )).join(' ');

    return (
      <svg className="sparkline-svg" width={width} height={height} aria-hidden="true">
        <path d={pathData} fill="none" stroke={strokeColor} strokeWidth="2" strokeLinecap="round" />
        {points.map((point, i) => point && <circle key={i} cx={point[0]} cy={point[1]} r="3" fill={strokeColor} />)}
      </svg>
    );
  };

  const cpuPoints = history.map((h) => h.metrics?.cpu_pct ?? null);
  const memPoints = history.map((h) => h.metrics?.memory_pct ?? null);
  const latPoints = history.map((h) => h.metrics?.latency_ms ?? null);
  const maxLat = Math.max(100, ...latPoints.filter((value) => value !== null));
  const format = (value: number | null | undefined, unit: string) => value == null ? '—' : `${value.toFixed(1)}${unit}`;

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
                    <th>Disk Read / Write</th>
                    <th>Network TX / RX</th>
                    <th>Receipt Digest</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map((pt) => (
                    <tr key={pt.payload_uuid}>
                      <td className="mono text-xs">{new Date(pt.event_time_utc).toLocaleTimeString(undefined, { timeZone: 'UTC' })} UTC</td>
                      <td>{format(pt.metrics?.cpu_pct, '%')}</td>
                      <td>{format(pt.metrics?.memory_pct, '%')}</td>
                      <td>{format(pt.metrics?.disk_used_pct, '%')}</td>
                      <td>{format(pt.metrics?.latency_ms, ' ms')}</td>
                      <td>{format(pt.metrics?.packet_loss_pct, '%')}</td>
                      <td>{format(pt.metrics?.disk_read_bps, ' B/s')} / {format(pt.metrics?.disk_write_bps, ' B/s')}</td>
                      <td>{format(pt.metrics?.net_tx_bps, ' B/s')} / {format(pt.metrics?.net_rx_bps, ' B/s')}</td>
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
