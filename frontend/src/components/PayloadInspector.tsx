import React, { useState } from 'react';
import type { PayloadDetail } from '../types/contracts';
import { apiClient } from '../api/client';
import { MOCK_PAYLOAD_SAMPLE } from '../fixtures/metadataFixtures';

interface PayloadInspectorProps {
  isFixtureMode: boolean;
}

export const PayloadInspector: React.FC<PayloadInspectorProps> = ({ isFixtureMode }) => {
  const [uuidInput, setUuidInput] = useState(MOCK_PAYLOAD_SAMPLE.payload_uuid);
  const [payload, setPayload] = useState<PayloadDetail | null>(isFixtureMode ? MOCK_PAYLOAD_SAMPLE : null);
  const [loading, setLoading] = useState(false);
  const [lookupError, setLookupError] = useState<string | null>(null);

  const handleLookup = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!uuidInput.trim()) return;

    if (isFixtureMode) {
      if (uuidInput.trim() === MOCK_PAYLOAD_SAMPLE.payload_uuid) {
        setPayload(MOCK_PAYLOAD_SAMPLE);
        setLookupError(null);
      } else {
        setLookupError(`Fixture ID not found in synthetic fixture store.`);
        setPayload(null);
      }
      return;
    }

    setLoading(true);
    setLookupError(null);
    try {
      const res = await apiClient.getPayload(uuidInput.trim());
      setPayload(res);
    } catch (err: unknown) {
      setLookupError((err as Error).message || 'Failed to retrieve payload metadata');
      setPayload(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="section-block payload-inspector-section">
      <div className="section-header">
        <h2 className="section-title">Received Payload Egress Inspector</h2>
        <span className="count-tag">Allow-Listed Metadata Only</span>
      </div>

      <div className="inspector-privacy-callout">
        <div className="callout-title">Privacy Verification Notice</div>
        <p>
          This view verifies centralized ingress adherence to the strict metadata allow-list.
          Central SaaS storage records only approved metrics and SHA-256 application body digests.
          Raw log lines, passwords, and source IP addresses are dropped locally at the edge.
        </p>
      </div>

      <form onSubmit={handleLookup} className="search-form">
        <label htmlFor="payload-uuid" className="input-label">Payload UUIDv5</label>
        <div className="search-row">
          <input
            id="payload-uuid"
            type="text"
            className="input-text mono"
            placeholder="e.g. e2b3c4d5-6789-5000-8000-abcdef123456"
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
        <div className="payload-metadata-grid">
          <div className="meta-item">
            <span className="meta-key">Payload UUID</span>
            <span className="meta-val mono">{payload.payload_uuid}</span>
          </div>
          <div className="meta-item">
            <span className="meta-key">Body SHA-256 Digest</span>
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
          <div className="meta-item full-width">
            <span className="meta-key">Approved Ingested Metrics</span>
            <pre className="code-block mono">
              {JSON.stringify(payload.metrics, null, 2)}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
};
