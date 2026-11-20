import { useState } from 'react';
import { apiClient, type ApiError } from '../api/client';

interface ConnectionBannerProps {
  serverStatus: 'connected' | 'disconnected' | 'fixture';
  error: ApiError | null;
  lastSyncUtc: string | null;
  isFixtureMode: boolean;
  onToggleFixtureMode: (enabled: boolean) => void;
  onRefresh: () => void;
  onCredentialsChanged: () => void;
  isLoading: boolean;
}

export function ConnectionBanner({
  serverStatus, error, lastSyncUtc, isFixtureMode, onToggleFixtureMode,
  onRefresh, onCredentialsChanged, isLoading,
}: ConnectionBannerProps) {
  const [credentialsOpen, setCredentialsOpen] = useState(true);
  const status = isFixtureMode ? 'Synthetic fixtures' : isLoading && !lastSyncUtc && !error
    ? 'Connecting' : serverStatus === 'connected' ? 'Live connection' : 'Disconnected';

  return (
    <section className="connection" aria-label="Data connection">
      <div className="connection-bar">
        <div className="connection-info">
          <span className={`connection-state state-${serverStatus}`}><i aria-hidden="true" />{status}</span>
          <span className="sync-time">{lastSyncUtc
            ? `Last sync ${new Date(lastSyncUtc).toLocaleTimeString('en-GB', { timeZone: 'UTC' })} UTC`
            : 'Awaiting first sync'}</span>
        </div>
        <div className="connection-actions">
          <button className="text-btn" aria-expanded={credentialsOpen} aria-controls="credentials" onClick={() => setCredentialsOpen(!credentialsOpen)}>Credentials</button>
          <button className="action-btn" onClick={() => { setCredentialsOpen(isFixtureMode); onToggleFixtureMode(!isFixtureMode); }}>
            {isFixtureMode ? 'Switch to Live API' : 'Use Mock Fixtures'}
          </button>
          <button className="action-btn" onClick={onRefresh} disabled={isLoading}><span aria-hidden="true">↻ </span>{isLoading ? 'Syncing…' : 'Sync now'}</button>
        </div>
      </div>
      {!isFixtureMode && error && (
        <p className="connection-error" role="alert">
          <strong>{error.status === 401 || error.status === 403 ? 'Authentication required.' : 'Fleet API unavailable.'}</strong>{' '}
          {error.status ? `${error.status} ${error.statusText}` : 'Network request failed'} · <code>{error.endpoint}</code>
          {lastSyncUtc && ' · Showing the last received readings.'}
        </p>
      )}
      {credentialsOpen && <form id="credentials" className="connection-form" onSubmit={(event) => {
        event.preventDefault();
        const form = new FormData(event.currentTarget);
        const tenant = String(form.get('tenant') ?? '').trim();
        const token = String(form.get('token') ?? '').trim();
        if (!tenant || !token) return;
        apiClient.setTenant(tenant, token);
        onCredentialsChanged();
      }}>
        <label>Tenant ID<input name="tenant" className="input-text mono" required defaultValue={apiClient.getTenantId()} /></label>
        <label>Operator token<input name="token" type="password" className="input-text" required autoComplete="off" placeholder="Enter operator token" /></label>
        <button className="btn-action-primary">Connect dashboard</button>
      </form>}
    </section>
  );
}
