import { useState } from 'react';
import type { PayloadDetail } from '../types/contracts';

const groups = {
  Utilization: [
    { field: 'cpu_pct', label: 'CPU', color: 'var(--chart-cpu)' },
    { field: 'memory_pct', label: 'Memory', color: 'var(--chart-memory)' },
  ],
  Latency: [{ field: 'latency_ms', label: 'Latency', color: 'var(--chart-latency)' }],
  Network: [
    { field: 'net_rx_bps', label: 'Receive', color: 'var(--chart-cpu)' },
    { field: 'net_tx_bps', label: 'Transmit', color: 'var(--chart-memory)' },
  ],
} as const;
type Group = keyof typeof groups;
const groupNames = Object.keys(groups) as Group[];
const number = new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 });
const clock = new Intl.DateTimeFormat(undefined, { timeZone: 'UTC', hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23' });

export function TelemetryChart({ samples, message }: { samples: PayloadDetail[]; message: string }) {
  const [group, setGroup] = useState<Group>('Utilization');
  const series = groups[group];
  const unit = group === 'Network' ? 'MiB/s' : group === 'Latency' ? 'ms' : '%';
  const rows = samples.map((sample) => ({
    time: Date.parse(sample.event_time_utc),
    values: series.map(({ field }) => {
      const raw = sample.metrics?.[field];
      return raw == null ? null : raw / (group === 'Network' ? 1048576 : 1);
    }),
  })).sort((a, b) => a.time - b.time);
  const values = rows.flatMap((row) => row.values).filter((v): v is number => v !== null);
  const start = rows[0]?.time;
  const end = rows.at(-1)?.time;
  const ceiling = group === 'Utilization' ? 100 : Math.max(1, Math.ceil(Math.max(...values)));
  return <div className="dev-telemetry">
    <div className="dev-metric-picker" role="group" aria-label="Chart metric">
      {groupNames.map((name) => <button type="button" key={name} aria-pressed={name === group} onClick={() => setGroup(name)}>{name}</button>)}
    </div>
    <figure className="dev-figure">
      <figcaption className="dev-readings">
        {series.map((line, i) => {
          const latest = rows.at(-1)?.values[i];
          return <div key={line.field}><span><i className={i ? 'dev-dashed' : ''} style={{ borderColor: line.color }} />{line.label}</span>
            <strong>{latest == null ? '—' : number.format(latest)} <small>{unit}</small></strong></div>;
        })}
      </figcaption>
      {values.length > 0 && start !== undefined && end !== undefined ? <>
        <div className="dev-plot">
          <div className="dev-scale" aria-hidden="true">{[ceiling, ceiling / 2, 0].map((v) => <span key={v}>{number.format(v)}</span>)}</div>
          <svg viewBox="0 0 600 150" preserveAspectRatio="none" role="img" aria-label={group + ' by event time in UTC, ' + samples.length + ' samples'}>
            {[3, 75, 147].map((y) => <line key={y} x1="0" x2="600" y1={y} y2={y} stroke="var(--line)" vectorEffect="non-scaling-stroke" />)}
            {series.map((line, i) => {
              let connected = false;
              const points: string[] = [];
              const path = rows.map(({ time, values: readings }) => {
                const v = readings[i];
                if (v === null) { connected = false; return ''; }
                const x = end === start ? 300 : 4 + 592 * (time - start) / (end - start);
                const y = 147 - 144 * v / ceiling;
                const point = x + ' ' + y;
                const command = (connected ? 'L' : 'M') + point;
                connected = true;
                points.push('M' + point + 'l0 0');
                return command;
              }).join(' ');
              return <g key={line.field} stroke={line.color} fill="none">
                <path d={path} strokeWidth="2" strokeDasharray={i ? '6 4' : undefined} vectorEffect="non-scaling-stroke" />
                <path d={points.join(' ')} strokeWidth="4" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
              </g>;
            })}
          </svg>
        </div>
        <div className="dev-axis"><time dateTime={new Date(start).toISOString()}>{clock.format(start)} UTC</time>
          {start !== end && <time dateTime={new Date(end).toISOString()}>{clock.format(end)} UTC</time>}</div>
      </> : <p className="dev-plot-empty">{message || 'No ' + group.toLowerCase() + ' readings in this sample window.'}</p>}
    </figure>
    {rows.length > 0 && <details className="dev-samples"><summary>Sample values ({rows.length})</summary>
      <div className="dev-scroll"><table className="telemetry-table"><thead><tr><th>Event time (UTC)</th>
        {series.map((line) => <th key={line.field}>{line.label} ({unit})</th>)}</tr></thead>
        <tbody>{rows.slice().reverse().map((row, i) => <tr key={i}><td>{new Date(row.time).toISOString()}</td>
          {row.values.map((v, j) => <td key={j}>{v === null ? '—' : number.format(v)}</td>)}</tr>)}</tbody></table></div>
    </details>}
  </div>;
}
