const form = document.getElementById('log-form');
const token = document.getElementById('token');
const picker = document.getElementById('log-file');
const importButton = document.getElementById('import-logs');
const exportButton = document.getElementById('export-logs');
const section = document.getElementById('report');
const status = document.getElementById('status');
const preview = document.getElementById('finding-preview');
const maxBytes = 5 * 1024 * 1024;
const set = (id, content) => { document.getElementById(id).textContent = content; };
let report = null;

function clearReport() {
  report = null;
  section.hidden = true;
  exportButton.disabled = true;
  status.textContent = '';
}

function displayReport(result) {
  const { parsed, total, malformed, metrics_analyzed, auth_analyzed, auth_failures,
    missing_timestamp, invalid_signals, unclassified, duplicate_metrics } = result.records;
  set('record-summary', `${result.format.toUpperCase()} · ${parsed} of ${total} records parsed · ${malformed} malformed`);
  set('analysis-summary', `${metrics_analyzed} metric records and ${auth_analyzed} authentication records analyzed · ${auth_failures} authentication failures recognized`);
  const levels = Object.entries(result.log_levels).map(([level, count]) => `${count} ${level}`).join(', ');
  set('level-summary', levels ? `Log levels · ${levels}` : 'No log levels recognized.');
  set('skipped-summary', `${missing_timestamp} without a usable timestamp · ${invalid_signals} invalid signals · ${duplicate_metrics} duplicate metric records · ${unclassified} without a recognized level or signal`);
  set('finding-summary', result.finding_count
    ? `${result.finding_count} ${result.finding_count === 1 ? 'finding' : 'findings'}. Showing up to 10 here. The report includes all findings.`
    : 'No metric anomaly or authentication burst detected in the analyzable records.');
  preview.hidden = result.finding_count === 0;
  preview.textContent = result.findings.slice(0, 10).map(finding => {
    const detail = finding.type === 'metric_anomaly'
      ? `${finding.metric} = ${finding.observed}`
      : `${finding.failed_attempts_count} authentication failures in ${finding.window_seconds}s`;
    return `Record ${finding.record} · ${finding.event_time_utc} · ${finding.severity} · ${detail}`;
  }).join('\n');
  section.hidden = false;
}

picker.addEventListener('change', clearReport);
form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const file = picker.files[0];
  if (!file || importButton.disabled) return;
  clearReport();
  if (file.size > maxBytes) {
    status.textContent = 'Choose a file up to 5 MiB.';
    return;
  }
  token.disabled = picker.disabled = importButton.disabled = true;
  status.textContent = 'Analyzing logs locally…';
  try {
    const response = await fetch('/api/local/log-review', {
      method: 'POST',
      headers: { Authorization: `Bearer ${token.value.trim()}`, 'Content-Type': 'application/octet-stream' },
      body: file,
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || 'Log review failed.');
    displayReport(result);
    report = result;
    exportButton.disabled = false;
    status.textContent = '';
  } catch (error) {
    status.textContent = error.message || 'Log review failed.';
  } finally {
    token.disabled = picker.disabled = importButton.disabled = false;
  }
});

exportButton.addEventListener('click', () => {
  if (!report) return;
  downloadJson(report, 'heimdal-log-review.json');
});

function downloadJson(data, filename) {
  const file = new Blob([JSON.stringify(data, null, 2), '\n'], { type: 'application/json' });
  const url = URL.createObjectURL(file);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

document.getElementById('export-proof').addEventListener('click', async (event) => {
  const button = event.currentTarget;
  button.disabled = true;
  try {
    const response = await fetch('/api/local/export/proof', {
      headers: { Authorization: `Bearer ${token.value.trim()}` }, cache: 'no-store',
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || 'Proof export failed.');
    downloadJson(result, 'heimdal-egress-proof.json');
    status.textContent = '';
  } catch (error) { status.textContent = error.message || 'Proof export failed.'; }
  finally { button.disabled = false; }
});
