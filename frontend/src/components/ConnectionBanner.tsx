import React from 'react';
import type { ApiError } from '../api/client';
import { IS_MOCK_FIXTURE_LABEL } from '../fixtures/metadataFixtures';

interface ConnectionBannerProps {
  serverStatus: 'connected' | 'disconnected' | 'fixture';
  error: ApiError | null;
  lastSyncUtc: string | null;
  tenantId: string;
  isFixtureMode: boolean;
  onToggleFixtureMode: (enabled: boolean) => void;
  onRefresh: () => void;
  onOpenSettings: () => void;
  isLoading: boolean;
}

export const ConnectionBanner: React.FC<ConnectionBannerProps> = ({
  serverStatus,
  error,
  lastSyncUtc,
  tenantId,
  isFixtureMode,
  onToggleFixtureMode,
  onRefresh,
  onOpenSettings,
  isLoading,
}) => {
  return (
    <header className="heimdal-header">
      <div className="header-top-row">
        <div className="brand-section">
          <span className="brand-badge">HEIMDAL</span>
          <h1 className="system-title">Operations & Fleet Monitoring</h1>
          <button
            type="button"
            className="tenant-tag-btn"
            onClick={onOpenSettings}
            title="Click to change operator credentials or tenant scope"
          >
            Tenant: {tenantId} &bull; Scope Settings
          </button>
        </div>

        <div className="status-controls">
          {isFixtureMode ? (
            <div className="fixture-badge-permanent" title="Displaying synthetic test metadata only">
              [ {IS_MOCK_FIXTURE_LABEL} ]
            </div>
          ) : serverStatus === 'connected' ? (
            <div className="live-status-pill status-live">
              <span className="dot dot-live" />
              LIVE SAAS INGEST (2.0s poll)
            </div>
          ) : (
            <div className="live-status-pill status-offline">
              <span className="dot dot-offline" />
              DISCONNECTED
            </div>
          )}

          <div className="action-buttons">
            <button
              type="button"
              className="settings-btn"
              onClick={onOpenSettings}
              title="Configure operator token and tenant scope"
            >
              Auth / Scope
            </button>
            <button
              type="button"
              className={`mode-toggle-btn ${isFixtureMode ? 'active-fixture' : ''}`}
              onClick={() => onToggleFixtureMode(!isFixtureMode)}
              title="Switch between live API connection and verified metadata fixtures"
            >
              {isFixtureMode ? 'Switch to Live API' : 'Use Mock Fixtures'}
            </button>
            <button
              type="button"
              className="refresh-btn"
              onClick={onRefresh}
              disabled={isLoading}
              title="Trigger immediate sync"
            >
              {isLoading ? 'Syncing...' : 'Sync Now'}
            </button>
          </div>
        </div>
      </div>

      {/* Disconnect/Error Callout: Never silently masked */}
      {!isFixtureMode && error && (
        <div className="error-callout" role="alert">
          <div className="error-title">Backend Connection Unreachable</div>
          <div className="error-detail">
            Status: {error.status === 0 ? 'Network Failure / Offline' : `${error.status} ${error.statusText}`} | Target: {error.endpoint}
          </div>
          <div className="error-hint">
            The central SaaS API is not responding. Showing honest disconnected state without silent fallback.
            You may switch to Mock Fixture mode above to test UI components.
          </div>
        </div>
      )}

      {/* Two-Window Architecture Notice (Per Hackathon Privacy Contract) */}
      <div className="two-tier-notice">
        <span className="notice-label">Two-Tier Privacy Isolation:</span>
        <span className="notice-text">
          This SaaS dashboard displays aggregated metadata only. Raw logs and secrets never leave the collector boundary.
          To view the local proof window, open <code>http://localhost:9001/audit</code> in a separate browser tab.
        </span>
        {lastSyncUtc && (
          <span className="sync-timestamp">Last sync: {new Date(lastSyncUtc).toLocaleTimeString(undefined, { timeZone: 'UTC' })} UTC</span>
        )}
      </div>
    </header>
  );
};
