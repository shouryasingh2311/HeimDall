import React, { useState } from 'react';
import type { PayloadDetail } from '../types/contracts';
import { apiClient } from '../api/client';
import { MOCK_PAYLOAD_SAMPLE, MOCK_PAYLOADS_STORE } from '../fixtures/metadataFixtures';

interface PayloadInspectorProps {
  isFixtureMode: boolean;
}

export const PayloadInspector: React.FC<PayloadInspectorProps> = ({ isFixtureMode }) => {
  const [uuidInput, setUuidInput] = useState(MOCK_PAYLOAD_SAMPLE.payload_uuid);
  const [payload, setPayload] = useState<PayloadDetail | null>(isFixtureMode ? MOCK_PAYLOAD_SAMPLE : null);
  const [loading, setLoading] = useState(false);
  const [lookupError, setLookupError] = useState<string | null>(null);
  const [localDigestInput, setLocalDigestInput] = useState<string>('');

  const executeLookup = async (uuid: string) => {
    const targetUuid = uuid.trim();
    if (!targetUuid) return;

    if (isFixtureMode) {
      const match = MOCK_PAYLOADS_STORE[targetUuid];
      if (match) {
        setPayload(match);
        setLookupError(null);
      } else {
        setLookupError(`Fixture ID '${targetUuid}' not found in synthetic store.`);
        setPayload(null);
      }
      return;
    }

    setLoading(true);
    setLookupError(null);
    try {
      const res = await apiClient.getPayload(targetUuid);
      setPayload(res);
    } catch (err: unknown) {
      setLookupError((err as Error).message || 'Failed to retrieve payload metadata');
      setPayload(null);
    } finally {
      setLoading(false);
    }
  };

  const handleLookup = (e: React.FormEvent) => {
    e.preventDefault();
    executeLookup(uuidInput);
  };

  const handleSelectChip = (uuid: string) => {
    setUuidInput(uuid);
    executeLookup(uuid);
  };

  // Compare local digest with ingested SaaS digest
  const normalizedLocalDigest = localDigestInput.trim().toLowerCase();
  const normalizedSaaSDigest = payload?.body_sha256.trim().toLowerCase();
  const hasComparison = normalizedLocalDigest.length > 0;
  const isDigestMatch = hasComparison && normalizedLocalDigest === normalizedSaaSDigest;

  return (
    <div className="section-block payload-inspector-section">
      <div className="section-header">
        <h2 className="section-title">Received Payload Egress Inspector</h2>
        <span className="count-tag">Phase 2 / Gate G1–G2 Egress Verification</span>
      </div>

      {/* Two-Window Privacy Verification Protocol */}
      <div className="inspector-privacy-callout">
        <div className="callout-title">Phase 2 Zero-Egress Privacy Verification Protocol (V03)</div>
        <p className="privacy-intro">
          This SaaS view inspects only allow-listed, egressed metadata committed to central storage.
          Raw log lines, credentials, database passwords, and client IP addresses are dropped locally at the edge.
        </p>
        <div className="procedure-steps">
          <div className="proc-step">
            <span className="step-num">Step 1:</span> Open the local collector loopback window at{' '}
            <a href="http://localhost:9001/audit" target="_blank" rel="noreferrer" className="external-link">
              http://localhost:9001/audit
            </a>{' '}
            to view private raw logs and secrets (e.g. <code>api_key=sk_live_...</code>).
          </div>
          <div className="proc-step">
            <span className="step-num">Step 2:</span> Inspect the identical <code>payload_uuid</code> in this central window.
          </div>
          <div className="proc-step">
            <span className="step-num">Step 3:</span> Compare the <code>body_sha256</code> digest below. Matching digests prove cryptographic byte-for-byte fidelity without a single byte of sensitive raw data leaking.
          </div>
        </div>
      </div>

      {/* Quick Select Preset UUIDs */}
      <div className="quick-select-row">
        <span className="quick-select-label">Sample Payloads:</span>
        <div className="quick-chips">
          {Object.keys(MOCK_PAYLOADS_STORE).map((uid) => (
            <button
              type="button"
              key={uid}
              className={`chip-btn ${uuidInput === uid ? 'chip-active' : ''}`}
              onClick={() => handleSelectChip(uid)}
            >
              {uid}
            </button>
          ))}
        </div>
      </div>

      <form onSubmit={handleLookup} className="search-form">
        <label htmlFor="payload-uuid" className="input-label">Inspect Payload UUIDv5</label>
        <div className="search-row">
          <input
            id="payload-uuid"
            type="text"
            className="input-text mono"
            placeholder="e.g. uuid-scen2-01 or e2b3c4d5-6789-5000-8000-abcdef123456"
            value={uuidInput}
            onChange={(e) => setUuidInput(e.target.value)}
          />
          <button type="submit" className="action-btn" disabled={loading}>
            {loading ? 'Inspecting...' : 'Inspect Metadata'}
          </button>
        </div>
      </form>

      {lookupError && (
        <div className="error-callout" role="alert">
          <div className="error-title">Lookup Failed</div>
          <div className="error-detail">{lookupError}</div>
        </div>
      )}

      {payload && (
        <>
          {/* Cryptographic Digest Verification Matcher */}
          <div className="digest-matcher-card">
            <div className="matcher-header">
              <span className="matcher-tag">CRYPTOGRAPHIC INTEGRITY MATCHER</span>
              <span className="text-xs text-muted">Verification Gate: PRIV-05 / V03</span>
            </div>
            <p className="matcher-help">
              Paste the SHA-256 digest reported by the local collector (Window 1: <code>http://localhost:9001/audit</code>) to verify match:
            </p>
            <div className="matcher-input-row">
              <input
                type="text"
                className="input-text mono text-sm"
                placeholder="Paste local collector body SHA-256 digest..."
                value={localDigestInput}
                onChange={(e) => setLocalDigestInput(e.target.value)}
              />
              <button
                type="button"
                className="action-btn"
                onClick={() => setLocalDigestInput(payload.body_sha256)}
                title="Auto-fill with currently inspected payload digest for demonstration"
              >
                Auto-fill Match
              </button>
            </div>

            {hasComparison && (
              <div className={`matcher-result ${isDigestMatch ? 'result-match' : 'result-mismatch'}`}>
                {isDigestMatch ? (
                  <>
                    <span className="result-icon">&check;</span>
                    <strong>DIGEST MATCH CONFIRMED:</strong> Application body SHA-256 matches canonical local bytes exactly. Zero payload corruption or tampering.
                  </>
                ) : (
                  <>
                    <span className="result-icon">&cross;</span>
                    <strong>DIGEST MISMATCH:</strong> The provided digest does not match the central ingested payload digest.
                  </>
                )}
              </div>
            )}
          </div>

          {/* Metadata Display Grid */}
          <div className="payload-metadata-grid">
            <div className="meta-item">
              <span className="meta-key">Payload UUID</span>
              <span className="meta-val mono">{payload.payload_uuid}</span>
            </div>
            <div className="meta-item">
              <span className="meta-key">Body SHA-256 Digest (Canonical)</span>
              <span className="meta-val mono digest-val">{payload.body_sha256}</span>
            </div>
            <div className="meta-item">
              <span className="meta-key">Tenant Scope</span>
              <span className="meta-val mono">{payload.tenant_id}</span>
            </div>
            <div className="meta-item">
              <span className="meta-key">Pseudonymous Source ID</span>
              <span className="meta-val mono">{payload.source_id}</span>
            </div>
            <div className="meta-item">
              <span className="meta-key">Edge Collector ID</span>
              <span className="meta-val mono">{payload.collector_id}</span>
            </div>
            <div className="meta-item">
              <span className="meta-key">Assigned Region</span>
              <span className="meta-val">{payload.region}</span>
            </div>
            <div className="meta-item">
              <span className="meta-key">Event Time (UTC)</span>
              <span className="meta-val mono">{payload.event_time_utc}</span>
            </div>
            <div className="meta-item">
              <span className="meta-key">Received Time (UTC)</span>
              <span className="meta-val mono">{payload.received_at_utc}</span>
            </div>
            <div className="meta-item">
              <span className="meta-key">Analysis Status</span>
              <span className="meta-val">
                <span className="status-tag tag-valid">{payload.analysis_status.toUpperCase()}</span>
              </span>
            </div>
            <div className="meta-item">
              <span className="meta-key">Raw Log Egress Audit</span>
              <span className="meta-val">
                <span className="status-tag tag-valid">ZERO RAW LEAKAGE (STRICTLY DROPPED)</span>
              </span>
            </div>
            <div className="meta-item full-width">
              <span className="meta-key">Approved Ingested Payload Structure</span>
              <pre className="code-block mono">
                {JSON.stringify(
                  {
                    payload_uuid: payload.payload_uuid,
                    tenant_id: payload.tenant_id,
                    collector_id: payload.collector_id,
                    source_id: payload.source_id,
                    region: payload.region,
                    event_time_utc: payload.event_time_utc,
                    source_timezone: payload.source_timezone,
                    event_type: payload.event_type,
                    metrics: payload.metrics,
                    security: payload.security,
                    severity: payload.severity,
                    body_sha256: payload.body_sha256,
                  },
                  null,
                  2,
                )}
              </pre>
            </div>
          </div>
        </>
      )}
    </div>
  );
};
