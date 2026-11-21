import { useCallback, useEffect, useState } from 'react';
import { apiClient } from '../api/client';
import { MOCK_SOURCE_METRICS_STORE, MOCK_TRANSITIONS_RESPONSE } from '../fixtures/metadataFixtures';
import type { FleetResponse, PayloadDetail, StateTransition } from '../types/contracts';
import { TelemetryChart } from './TelemetryChart';
import './dev-dashboard.css';

type Load<T> = () => Promise<{ items: T[] }>;
function useFeed<T>(load: Load<T> | null, fixtureRows?: T[]) {
  const [last, setLast] = useState<{ load: Load<T>; rows?: T[]; failed: boolean }>();
  useEffect(() => {
    if (!load || fixtureRows) return;
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    async function refresh(fetchRows: Load<T>) {
      try {
        const { items } = await fetchRows();
        if (active) setLast({ load: fetchRows, rows: items, failed: false });
      } catch {
        if (active) setLast((prev) => ({ load: fetchRows, rows: prev?.load === fetchRows ? prev.rows : undefined, failed: true }));
      } finally {
        if (active) timer = setTimeout(() => void refresh(fetchRows), 5000);
      }
    }
    void refresh(load);
    return () => { active = false; clearTimeout(timer); };
  }, [load, fixtureRows]);
  const current = last?.load === load ? last : undefined;
  return { rows: fixtureRows ?? current?.rows ?? [], failed: !!current?.failed, loading: !!load && !fixtureRows && !current };
}

const getTransitions = () => apiClient.getTransitions();
const noSamples: PayloadDetail[] = [];
const healthStates = ['Excellent', 'Good', 'Fair', 'Poor'] as const;

function FleetDiagnostics({ fleet }: { fleet: FleetResponse | null }) {
  return <aside className="dev-side" aria-label="Fleet diagnostics">
    <section className="section-block"><div className="dev-heading"><h2>Source health</h2><span>{fleet ? fleet.sources.length + ' sources' : 'Awaiting fleet'}</span></div>
      {fleet && <ul className="dev-health">{healthStates.map((state) => {
        const count = fleet.sources.filter((source) => source.health === state).length;
        return <li key={state}><span>{state}</span><span className="dev-track"><i data-health={state} style={{ width: (100 * count / (fleet.sources.length || 1)) + '%' }} /></span><b>{count}</b></li>;
      })}</ul>}
    </section>
    <section className="section-block"><div className="dev-heading"><h2>Collector outboxes</h2></div>
      {fleet?.collectors.length ? <ul className="dev-outboxes">{fleet.collectors.map((c) => <li key={c.collector_id}>
        <b>{c.collector_id}</b><strong>{c.queue_depth.toLocaleString()} queued</strong>
        <small>CPU {c.cpu_pct}% · RSS {c.rss_mb} MB</small>
      </li>)}</ul> : <p>{fleet ? 'No collectors reported.' : 'Awaiting collector data.'}</p>}
    </section>
  </aside>;
}

function EventLog({ samples, transitions, pending, onInspect }: {
  samples: PayloadDetail[]; transitions: StateTransition[]; pending: boolean; onInspect: (uuid: string) => void;
}) {
  const [query, setQuery] = useState('');
  const [kind, setKind] = useState('all');
  const rows = [
    ...samples.map((s) => ({ id: s.payload_uuid, time: s.event_time_utc, kind: 'Sample', entity: s.source_id, detail: s.event_type + ' · ' + s.severity + ' · ' + s.analysis_status })),
    ...transitions.map((t) => ({ id: t.transition_id, time: t.timestamp_utc, kind: 'Transition', entity: t.entity_id, detail: [t.from_state + ' → ' + t.to_state, ...t.reason_codes].join(' · ') })),
  ].filter((r) => (kind === 'all' || r.kind === kind) && [r.entity, r.detail, r.id, r.kind, r.time].join(' ').toLowerCase().includes(query.trim().toLowerCase()))
    .sort((a, b) => Date.parse(b.time) - Date.parse(a.time));
  return <section className="section-block dev-log">
    <div className="dev-heading"><div><h2>Event log</h2><p>Selected source samples and fleet-wide health transitions, newest first.</p></div></div>
    <div className="dev-filters"><label>Search events<input type="search" placeholder="Entity, reason, or ID" value={query} onChange={(e) => setQuery(e.target.value)} /></label>
      <label>Event type<select value={kind} onChange={(e) => setKind(e.target.value)}><option value="all">All events</option><option value="Sample">Samples</option><option value="Transition">Transitions</option></select></label>
      <span>{rows.length} {rows.length === 1 ? 'event' : 'events'}</span>
    </div>
    {rows.length ? <div className="dev-scroll" tabIndex={0} role="region" aria-label="Recent events"><table className="telemetry-table">
      <thead><tr><th>Time (UTC)</th><th>Type</th><th>Entity</th><th>Detail</th><th><span className="dev-sr">Payload</span></th></tr></thead>
      <tbody>{rows.map((r) => <tr key={r.kind + r.id}>
        <td><time dateTime={r.time}>{new Date(r.time).toISOString().replace('T', ' ').slice(0, 19)}</time></td>
        <td>{r.kind}</td><td>{r.entity}</td><td>{r.detail}</td><td>{r.kind === 'Sample' && <button className="text-btn" aria-label={'Inspect payload ' + r.id} onClick={() => onInspect(r.id)}>Inspect</button>}</td>
      </tr>)}</tbody></table></div> : <p>{query || kind !== 'all' ? 'No events match these filters.' : pending ? 'Loading events…' : 'No recent events available.'}</p>}
  </section>;
}

export function DevDashboard({ fleet, fixture, onInspect }: { fleet: FleetResponse | null; fixture: boolean; onInspect: (uuid: string) => void }) {
  const [chosen, setChosen] = useState('');
  const sources = fleet?.sources ?? [];
  const preferred = fixture ? sources.find((s) => MOCK_SOURCE_METRICS_STORE[s.source_id]?.length) : undefined;
  const source = sources.find((s) => s.source_id === chosen)?.source_id ?? preferred?.source_id ?? sources[0]?.source_id ?? '';
  const getSamples = useCallback(() => apiClient.getSourceMetrics(source, 50, undefined, true), [source]);
  const samples = useFeed(source ? getSamples : null, fixture ? MOCK_SOURCE_METRICS_STORE[source] ?? noSamples : undefined);
  const transitions = useFeed(getTransitions, fixture ? MOCK_TRANSITIONS_RESPONSE.items : undefined);
  const empty = !source ? 'Waiting for a source to report.' : samples.loading ? 'Loading source history…' : samples.failed ? 'Source history is unavailable.' : '';
  return <div className="dev-dashboard">
    <div className="dev-grid">
      <section className="section-block dev-history"><div className="dev-heading">
        <div><h2>Source telemetry</h2><p>Latest 50 samples by event time.</p></div>
        <label>Source<select value={source} disabled={!sources.length} onChange={(e) => setChosen(e.target.value)}>
          {!sources.length && <option value="">No sources</option>}
          {sources.map((s) => <option key={s.source_id} value={s.source_id}>{s.source_id}</option>)}
        </select></label>
      </div>
        <TelemetryChart samples={samples.rows} message={empty} />
      </section>
      <FleetDiagnostics fleet={fleet} />
    </div>
    {(samples.failed || transitions.failed) && <p className="dev-warning" role="status">
      Refresh failed for {[samples.failed && 'source history', transitions.failed && 'health transitions'].filter(Boolean).join(' and ')}. Showing available records while retrying.
    </p>}
    <EventLog samples={samples.rows} transitions={transitions.rows} pending={samples.loading || transitions.loading} onInspect={onInspect} />
  </div>;
}
