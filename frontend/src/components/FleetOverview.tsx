import React, { useCallback, useState, useEffect, useRef } from 'react';
import type { FleetResponse, FleetSource, HealthState } from '../types/contracts';
import { apiClient } from '../api/client';
import { SourceMetricsModal } from './SourceMetricsModal';

interface FleetOverviewProps {
  data: FleetResponse | null;
  isLoading: boolean;
  isFixtureMode: boolean;
  onInspectPayload?: (uuid: string) => void;
}

const getHealthBadgeClass = (health: HealthState): string => {
  switch (health) {
    case 'Excellent':
      return 'badge-health-excellent';
    case 'Good':
      return 'badge-health-good';
    case 'Fair':
      return 'badge-health-fair';
    case 'Poor':
      return 'badge-health-poor';
    default:
      return 'badge-health-unknown';
  }
};

export const FleetOverview: React.FC<FleetOverviewProps> = ({
  data,
  isLoading,
  isFixtureMode,
  onInspectPayload,
}) => {
  const fleet = useRef<HTMLDivElement>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const closeTrends = useCallback(() => setSelectedId(null), []);
  const selectedSource: FleetSource | null = data?.sources.find((src) => src.source_id === selectedId) ?? null;

  useEffect(() => {
    if (!fleet.current || !data || isFixtureMode || selectedId) return;
    const frameIds = new Set<number>();
    const observer = new IntersectionObserver((entries) => {
      for (const { isIntersecting, target } of entries) {
        const uuid = (target as HTMLElement).dataset.payloadUuid;
        if (!isIntersecting || !uuid || document.visibilityState !== 'visible') continue;
        const first = requestAnimationFrame(() => {
          frameIds.delete(first);
          const second = requestAnimationFrame(() => {
            frameIds.delete(second);
            const rect = target.getBoundingClientRect();
            if (target.isConnected && (target as HTMLElement).dataset.payloadUuid === uuid
                && rect.bottom > 0 && rect.top < window.innerHeight && document.visibilityState === 'visible') {
              void apiClient.recordFirstRender(uuid);
            }
          });
          frameIds.add(second);
        });
        frameIds.add(first);
      }
    });
    fleet.current.querySelectorAll('[data-payload-uuid]').forEach((row) => observer.observe(row));
    return () => {
      observer.disconnect();
      frameIds.forEach((id) => cancelAnimationFrame(id));
    };
  }, [data, isFixtureMode, selectedId]);

  if (isLoading && !data) {
    return (
      <div className="card loading-card">
        <div className="skeleton-line" />
        <div className="skeleton-line short" />
        <p className="loading-text">Polling fleet infrastructure state...</p>
      </div>
    );
  }

  if (!data || (data.collectors.length === 0 && data.sources.length === 0)) {
    return (
      <div className="card empty-card">
        <h3>No Active Telemetry Received</h3>
        <p>No collectors or sources have registered with tenant scope yet.</p>
      </div>
    );
  }

  return (
    <div className="fleet-container" ref={fleet}>
      {/* Collectors Section */}
      <section className="section-block">
        <div className="section-header">
          <h2 className="section-title">Edge Telemetry Collectors</h2>
          <span className="count-tag">{data.collectors.length} Registered</span>
        </div>

        <div className="table-responsive">
          <table className="telemetry-table">
            <thead>
              <tr>
                <th>Collector ID</th>
                <th>Version</th>
                <th>Health State</th>
                <th>Queue Depth</th>
                <th>CPU %</th>
                <th>RSS Memory</th>
                <th>Config</th>
                <th>Last Heartbeat</th>
                <th>Reasons</th>
              </tr>
            </thead>
            <tbody>
              {data.collectors.map((col) => (
                <tr key={col.collector_id}>
                  <td className="mono font-semibold">{col.collector_id}</td>
                  <td>{col.version}</td>
                  <td>
                    <span className={`health-badge ${getHealthBadgeClass(col.health)}`}>
                      {col.health}
                    </span>
                  </td>
                  <td>
                    <span className={`metric-value ${col.queue_depth > 0 ? 'metric-warn' : ''}`}>
                      {col.queue_depth} msgs
                    </span>
                  </td>
                  <td>{col.cpu_pct.toFixed(1)}%</td>
                  <td>{col.rss_mb.toFixed(1)} MB</td>
                  <td>
                    <span className={`status-tag ${col.config_status === 'valid' ? 'tag-valid' : 'tag-alert'}`}>
                      {col.config_status.toUpperCase()}
                    </span>
                  </td>
                  <td className="mono text-muted text-sm">
                    {new Date(col.last_heartbeat_utc).toLocaleTimeString(undefined, { timeZone: 'UTC' })} UTC
                  </td>
                  <td>
                    <div className="reason-chips">
                      {col.reasons.map((r, i) => (
                        <span key={i} className="chip">{r}</span>
                      ))}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Pseudonymous Sources Section */}
      <section className="section-block">
        <div className="section-header">
          <h2 className="section-title">Monitored Service Sources (Pseudonymized)</h2>
          <span className="count-tag">{data.sources.length} Active</span>
        </div>

        <div className="table-responsive">
          <table className="telemetry-table">
            <thead>
              <tr>
                <th>Source ID</th>
                <th>Collector</th>
                <th>Health State</th>
                <th>CPU %</th>
                <th>Memory %</th>
                <th>Latency</th>
                <th>Loss</th>
                <th>Service Avail.</th>
                <th>Connectivity</th>
                <th>Latest Event</th>
                <th>Active Reasons</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {data.sources.map((src) => (
                <tr key={src.source_id} data-payload-uuid={src.payload_uuid}>
                  <td className="mono font-semibold">{src.source_id}</td>
                  <td className="mono text-muted text-sm">{src.collector_id}</td>
                  <td>
                    <span className={`health-badge ${getHealthBadgeClass(src.health)}`}>
                      {src.health}
                    </span>
                  </td>
                  <td>{src.metrics.cpu_pct !== null ? `${src.metrics.cpu_pct.toFixed(1)}%` : '—'}</td>
                  <td>{src.metrics.memory_pct !== null ? `${src.metrics.memory_pct.toFixed(1)}%` : '—'}</td>
                  <td>{src.metrics.latency_ms !== null ? `${src.metrics.latency_ms.toFixed(1)} ms` : '—'}</td>
                  <td>{src.metrics.packet_loss_pct !== null ? `${src.metrics.packet_loss_pct.toFixed(1)}%` : '—'}</td>
                  <td>
                    <span className={`status-tag ${src.metrics.service_available === false ? 'tag-alert' : ''}`}>
                      {src.metrics.service_available === null ? '—' : src.metrics.service_available ? 'NOMINAL' : 'DEGRADED'}
                    </span>
                  </td>
                  <td>{src.metrics.connectivity === null ? '—' : src.metrics.connectivity ? 'Up' : 'Down'}</td>
                  <td className="mono text-muted text-sm">
                    {new Date(src.latest_event_time_utc).toLocaleTimeString(undefined, { timeZone: 'UTC' })} UTC
                  </td>
                  <td>
                    <div className="reason-chips">
                      {src.reason_codes.map((rc, i) => (
                        <span key={i} className="chip">{rc}</span>
                      ))}
                    </div>
                  </td>
                  <td>
                    <button
                      type="button"
                      className="action-btn text-xs"
                      onClick={() => setSelectedId(src.source_id)}
                    >
                      View Trends
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Phase 4 Source Metrics Modal */}
      <SourceMetricsModal
        source={selectedSource}
        onClose={closeTrends}
        isFixtureMode={isFixtureMode}
        onInspectPayload={onInspectPayload}
      />
    </div>
  );
};
