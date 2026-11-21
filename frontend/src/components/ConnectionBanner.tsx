import type { ApiError } from '../api/client';

interface ConnectionBannerProps {
  serverStatus: 'connected' | 'disconnected' | 'fixture';
  error: ApiError | null;
  lastSyncUtc: string | null;
  isFixtureMode: boolean;
  onToggleFixtureMode: (enabled: boolean) => void;
  onRefresh: () => void;
  isLoading: boolean;
}

export function ConnectionBanner({
  serverStatus, error, lastSyncUtc, isFixtureMode, onToggleFixtureMode,
  onRefresh, isLoading,
}: ConnectionBannerProps) {
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
          <button className="action-btn" onClick={() => onToggleFixtureMode(!isFixtureMode)}>
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
    </section>
  );
}
