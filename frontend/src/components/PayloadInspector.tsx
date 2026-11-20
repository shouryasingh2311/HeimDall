import { CollectorLink } from './CollectorLink';
import React, { useState } from 'react';
import type { PayloadDetail } from '../types/contracts';
import { apiClient } from '../api/client';
import { MOCK_PAYLOAD_SAMPLE, MOCK_PAYLOADS_STORE } from '../fixtures/metadataFixtures';

interface PayloadInspectorProps {
  isFixtureMode: boolean;
  initialUuid?: string;
}

export const PayloadInspector: React.FC<PayloadInspectorProps> = ({ isFixtureMode, initialUuid }) => {
  const [uuidInput, setUuidInput] = useState(initialUuid || (isFixtureMode ? MOCK_PAYLOAD_SAMPLE.payload_uuid : ''));
  const [payload, setPayload] = useState<PayloadDetail | null>(isFixtureMode ? MOCK_PAYLOAD_SAMPLE : null);
  const [loading, setLoading] = useState(false);
  const [lookupError, setLookupError] = useState<string | null>(null);
  const [localDigestInput, setLocalDigestInput] = useState<string>('');

  React.useEffect(() => {
    if (initialUuid) {
      setUuidInput(initialUuid);
      executeLookup(initialUuid);
    }
  }, [initialUuid]);

  const executeLookup = async (uuid: string) => {
    const targetUuid = uuid.trim();
    if (!targetUuid || loading) return;
    setLocalDigestInput('');
    setPayload(null);

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
  const isDigestMatch = /^[a-f0-9]{64}$/.test(normalizedLocalDigest) && normalizedLocalDigest === normalizedSaaSDigest;

  return (
    <div className="section-block payload-inspector-section">
      <div className="section-header"><h2 className="section-title">Find a payload</h2></div>
      <details className="inspector-privacy-callout">
        <summary>How to verify a collector receipt</summary>
        <ol className="procedure-steps">
          <li>Open the <CollectorLink page="audit">local egress proof</CollectorLink> to inspect the masked preview and outbound bytes.</li>
          <li>Look up the same payload UUID here. The central store receives only approved metadata.</li>
          <li>Compare the collector’s SHA-256 digest with the digest on the receipt.</li>
        </ol>
      </details>

      {/* Quick Select Preset UUIDs */}
      {isFixtureMode && <div className="quick-select-row">
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
      </div>}

      <form onSubmit={handleLookup} className="search-form">
        <label htmlFor="payload-uuid" className="input-label">Inspect Payload UUIDv5</label>
        <div className="search-row">
          <input
            id="payload-uuid"
            type="text"
            className="input-text mono"
            placeholder={isFixtureMode ? 'e.g. uuid-scen2-01' : 'Paste the collector payload UUID'}
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
              <span className="matcher-tag">Compare SHA-256 digests</span>
            </div>
            <p className="matcher-help">
              Paste the digest from the local egress proof.
            </p>
            <div className="matcher-input-row">
              <input
                type="text"
                aria-label="Local collector SHA-256 digest"
                maxLength={64}
                className="input-text mono text-sm"
                placeholder="Paste local collector body SHA-256 digest..."
                value={localDigestInput}
                onChange={(e) => setLocalDigestInput(e.target.value)}
              />
            </div>

            {hasComparison && (
              <div className={`matcher-result ${isDigestMatch ? 'result-match' : 'result-mismatch'}`}>
                {isDigestMatch ? (
                  <>
                    <span className="result-icon">&check;</span>
                    <strong>{isFixtureMode ? 'SYNTHETIC DIGEST MATCH' : 'DIGEST MATCH CONFIRMED'}:</strong> Local and received body digests agree.
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
              <span className="meta-key">Receipt contents</span>
              <span className="meta-val">
                <span className="status-tag tag-valid">APPROVED METADATA</span>
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
