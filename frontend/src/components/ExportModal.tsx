import { useState } from 'react';
import { Dialog } from './Dialog';
import { apiClient } from '../api/client';

interface ExportModalProps {
  onClose: () => void;
}

export function ExportModal({ onClose }: ExportModalProps) {
  const [downloading, setDownloading] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [isError, setIsError] = useState(false);

  const handleDownload = async (endpoint: string, filename: string, label: string) => {
    try {
      setDownloading(label);
      setStatusMessage(null);
      setIsError(false);
      await apiClient.downloadExport(endpoint, filename);
      setStatusMessage(`Downloaded ${label} successfully.`);
    } catch (err: unknown) {
      setIsError(true);
      setStatusMessage(`Failed to export ${label}: ${(err as Error).message || 'Server error'}`);
    } finally {
      setDownloading(null);
    }
  };

  return (
    <Dialog titleId="export-dialog-title" large onClose={onClose}>
      <div className="modal-header">
        <h2 id="export-dialog-title" className="modal-title">Export Telemetry & Proofs</h2>
        <button type="button" className="modal-close-btn" aria-label="Close export dialog" onClick={onClose}>
          ✕
        </button>
      </div>

      <p className="modal-intro text-sm text-muted">
        Export central metadata stored by Heimdal SaaS or local cryptographic egress proofs from the edge collector.
        Strict zero-leakage guarantee: raw payloads and unknown fields are never included.
      </p>

      {statusMessage && (
        <div className={isError ? 'connection-error mb-3' : 'connection-state mb-3'} style={{ padding: '8px 12px' }}>
          <span>{statusMessage}</span>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px', margin: '20px 0' }}>
        {/* Full Bundle Card */}
        <div className="section-block" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
              <span className="font-semibold">Complete Tenant Bundle</span>
              <span className="count-tag">ZIP Archive</span>
            </div>
            <p className="text-xs text-muted mb-3">
              Full bundle containing metrics.csv, transitions.csv, incident_report.md, incidents.json, and remediation_audit.csv.
            </p>
          </div>
          <button
            type="button"
            className="btn-action-primary"
            disabled={downloading !== null}
            onClick={() => handleDownload('/api/v1/export/bundle', `heimdall-export-${apiClient.getTenantId()}.zip`, 'Full Bundle (ZIP)')}
          >
            {downloading === 'Full Bundle (ZIP)' ? 'Generating ZIP...' : 'Download Full Bundle (.zip)'}
          </button>
        </div>

        {/* Metrics Card */}
        <div className="section-block" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
              <span className="font-semibold">Metrics Telemetry</span>
              <span className="count-tag">Timeseries</span>
            </div>
            <p className="text-xs text-muted mb-3">
              Allow-listed CPU, memory, disk, network, latency, and packet loss metrics across all tenant sources.
            </p>
          </div>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              type="button"
              className="action-btn"
              style={{ flex: 1 }}
              disabled={downloading !== null}
              onClick={() => handleDownload('/api/v1/export/metrics?format=csv', 'metrics.csv', 'Metrics (CSV)')}
            >
              CSV
            </button>
            <button
              type="button"
              className="action-btn"
              style={{ flex: 1 }}
              disabled={downloading !== null}
              onClick={() => handleDownload('/api/v1/export/metrics?format=json', 'metrics.json', 'Metrics (JSON)')}
            >
              JSON
            </button>
          </div>
        </div>

        {/* Incidents Card */}
        <div className="section-block" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
              <span className="font-semibold">AIOps Incidents</span>
              <span className="count-tag">Analysis</span>
            </div>
            <p className="text-xs text-muted mb-3">
              Correlated incidents with anomaly z-scores, baselines, evidence scores, and recommended remediation actions.
            </p>
          </div>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              type="button"
              className="action-btn"
              style={{ flex: 1 }}
              disabled={downloading !== null}
              onClick={() => handleDownload('/api/v1/export/incidents?format=markdown', 'incident_report.md', 'Incidents (Markdown)')}
            >
              Report (.md)
            </button>
            <button
              type="button"
              className="action-btn"
              style={{ flex: 1 }}
              disabled={downloading !== null}
              onClick={() => handleDownload('/api/v1/export/incidents?format=json', 'incidents.json', 'Incidents (JSON)')}
            >
              JSON
            </button>
          </div>
        </div>

        {/* Transitions Card */}
        <div className="section-block" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
              <span className="font-semibold">Health Transitions</span>
              <span className="count-tag">State Audit</span>
            </div>
            <p className="text-xs text-muted mb-3">
              Chronological log of entity state changes (HEALTHY, DEGRADED, UNHEALTHY) with trigger reasons.
            </p>
          </div>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              type="button"
              className="action-btn"
              style={{ flex: 1 }}
              disabled={downloading !== null}
              onClick={() => handleDownload('/api/v1/export/transitions?format=csv', 'transitions.csv', 'Transitions (CSV)')}
            >
              CSV
            </button>
            <button
              type="button"
              className="action-btn"
              style={{ flex: 1 }}
              disabled={downloading !== null}
              onClick={() => handleDownload('/api/v1/export/transitions?format=json', 'transitions.json', 'Transitions (JSON)')}
            >
              JSON
            </button>
          </div>
        </div>

        {/* Remediation Audit Card */}
        <div className="section-block" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
              <span className="font-semibold">Remediation Log</span>
              <span className="count-tag">Actions</span>
            </div>
            <p className="text-xs text-muted mb-3">
              Audit trail of automated and manual remediation actions, policies applied, and execution outcomes.
            </p>
          </div>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              type="button"
              className="action-btn"
              style={{ flex: 1 }}
              disabled={downloading !== null}
              onClick={() => handleDownload('/api/v1/export/remediation?format=csv', 'remediation_audit.csv', 'Remediation (CSV)')}
            >
              CSV
            </button>
            <button
              type="button"
              className="action-btn"
              style={{ flex: 1 }}
              disabled={downloading !== null}
              onClick={() => handleDownload('/api/v1/export/remediation?format=json', 'remediation_audit.json', 'Remediation (JSON)')}
            >
              JSON
            </button>
          </div>
        </div>

        {/* Edge Proof Card */}
        <div className="section-block" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
              <span className="font-semibold">Local Egress Proof</span>
              <span className="count-tag">Cryptographic</span>
            </div>
            <p className="text-xs text-muted mb-3">
              Direct from local collector outbox: cryptographic proof with SHA-256 digests and SaaS receipts.
            </p>
          </div>
          <button
            type="button"
            className="action-btn"
            disabled={downloading !== null}
            onClick={() => handleDownload('http://localhost:9001/api/local/export/proof', 'egress_proof.json', 'Egress Proof (JSON)')}
          >
            Download Proof (JSON)
          </button>
        </div>
      </div>

      <div className="modal-footer" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span className="text-xs text-muted">
          Auth: Bearer token for tenant <code>{apiClient.getTenantId()}</code>
        </span>
        <button type="button" className="action-btn" onClick={onClose}>
          Close
        </button>
      </div>
    </Dialog>
  );
}
