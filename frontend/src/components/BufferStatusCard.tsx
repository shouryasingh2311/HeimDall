import type { CSSProperties } from 'react';
import type { FleetResponse } from '../types/contracts';

export function BufferStatusCard({ data }: { data: FleetResponse | null }) {
  const collectors = data?.collectors ?? [];
  const healthy = collectors.filter(({ health }) => health === 'Excellent' || health === 'Good').length;
  const hasCollectors = collectors.length > 0;
  const depth = collectors.reduce((sum, collector) => sum + collector.queue_depth, 0);
  const dialStyle = { '--sweep': `${hasCollectors ? healthy / collectors.length * 360 : 0}deg` } as CSSProperties;

  return (
    <section className="fleet-summary" aria-labelledby="summary-title">
      <h2 id="summary-title">Telemetry snapshot</h2>
      <dl className="readings">
        <div className="collector-reading">
          <dt>Healthy collectors</dt>
          <dd className="dial" style={dialStyle}>
            <span>{data ? healthy : '—'}{data && <small> / {collectors.length}</small>}</span>
          </dd>
          <dd className="reading-caption">Good or excellent health</dd>
        </div>
        <div className="instrument">
          <dt>Monitored sources</dt>
          <dd>{data ? data.sources.length : '—'}</dd>
          <dd className="reading-caption">Pseudonymous services</dd>
        </div>
        <div className="instrument">
          <dt>Outbox depth</dt>
          <dd>{hasCollectors ? depth : '—'}</dd>
          <dd className="reading-caption">Records awaiting delivery</dd>
        </div>
      </dl>
      <p className="receipt-note">Delivery is confirmed by a committed receipt and matching SHA-256 digest.</p>
    </section>
  );
}
