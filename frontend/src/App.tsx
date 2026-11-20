import { useCallback, useState } from 'react';
import { useFleetPolling } from './hooks/useFleetPolling';
import { ConnectionBanner } from './components/ConnectionBanner';
import { BufferStatusCard } from './components/BufferStatusCard';
import { FleetOverview } from './components/FleetOverview';
import { PayloadInspector } from './components/PayloadInspector';
import { TransitionsView } from './components/TransitionsView';
import { IncidentDetailView } from './components/IncidentDetailView';
import { ScenarioResultsView } from './components/ScenarioResultsView';
import { OperatorSettingsModal } from './components/OperatorSettingsModal';
import { apiClient } from './api/client';
import { BenchmarkPanel } from './components/BenchmarkPanel';

type TabKey = 'fleet' | 'inspector' | 'incidents' | 'scenarios';

export function App() {
  const [session, setSession] = useState(0);
  const resetDashboard = useCallback(() => setSession((value) => value + 1), []);

  return (
    <>
      <form className="search-form" onSubmit={(event) => {
        event.preventDefault();
        const form = event.currentTarget;
        const data = new FormData(form);
        const tenant = String(data.get('tenant') ?? '').trim();
        const token = String(data.get('token') ?? '').trim();
        if (!tenant || !token) return;
        apiClient.setTenant(tenant, token);
        form.reset();
        resetDashboard();
      }}>
        <label>Tenant ID <input name="tenant" required className="input-text" /></label>
        <label>Operator token <input name="token" type="password" required autoComplete="off" className="input-text" /></label>
        <button className="action-btn">Connect dashboard</button>
      </form>
      <Dashboard key={session} onCredentialsChanged={resetDashboard} />
    </>
  );
}

function Dashboard({ onCredentialsChanged }: { onCredentialsChanged: () => void }) {
  const [activeTab, setActiveTab] = useState<TabKey>('fleet');
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [inspectPayloadUuid, setInspectPayloadUuid] = useState<string | undefined>(undefined);
  const {
    data,
    isLoading,
    error,
    isFixtureMode,
    lastSyncUtc,
    serverStatus,
    refreshNow,
    setFixtureMode,
  } = useFleetPolling(2000);

  const handleInspectPayload = (uuid: string) => {
    setInspectPayloadUuid(uuid);
    setActiveTab('inspector');
  };

  return (
    <div className="cicada-app-shell">
      <ConnectionBanner
        serverStatus={serverStatus}
        error={error}
        lastSyncUtc={lastSyncUtc}
        tenantId={apiClient.getTenantId()}
        isFixtureMode={isFixtureMode}
        onToggleFixtureMode={setFixtureMode}
        onRefresh={refreshNow}
        onOpenSettings={() => setIsSettingsOpen(true)}
        isLoading={isLoading}
      />

      <nav className="tab-navigation" aria-label="Dashboard views">
        <button
          type="button"
          className={`tab-btn ${activeTab === 'fleet' ? 'active' : ''}`}
          onClick={() => setActiveTab('fleet')}
        >
          Fleet &amp; Health State
        </button>
        <button
          type="button"
          className={`tab-btn ${activeTab === 'inspector' ? 'active' : ''}`}
          onClick={() => setActiveTab('inspector')}
        >
          Payload Egress Inspector
        </button>
        <button
          type="button"
          className={`tab-btn ${activeTab === 'incidents' ? 'active' : ''}`}
          onClick={() => setActiveTab('incidents')}
        >
          AIOps Incidents &amp; Remediation
        </button>
        <button
          type="button"
          className={`tab-btn ${activeTab === 'scenarios' ? 'active' : ''}`}
          onClick={() => setActiveTab('scenarios')}
        >
          Scenario Verification (1–8)
        </button>
      </nav>

      <main className="cicada-main-content">
        {activeTab === 'fleet' && (
          <div className="tab-pane">
            <BufferStatusCard
              collectors={data?.collectors || []}
              sources={data?.sources || []}
              isFixtureMode={isFixtureMode}
            />
            <FleetOverview
              data={data}
              isLoading={isLoading}
              isFixtureMode={isFixtureMode}
              onInspectPayload={handleInspectPayload}
            />
            <TransitionsView isFixtureMode={isFixtureMode} />
            {!isFixtureMode && <BenchmarkPanel />}
          </div>
        )}

        {activeTab === 'inspector' && (
          <div className="tab-pane">
            <PayloadInspector key={String(isFixtureMode)} isFixtureMode={isFixtureMode} initialUuid={inspectPayloadUuid} />
          </div>
        )}

        {activeTab === 'incidents' && (
          <div className="tab-pane">
            <IncidentDetailView
              isFixtureMode={isFixtureMode}
              onInspectPayload={handleInspectPayload}
            />
          </div>
        )}

        {activeTab === 'scenarios' && (
          <div className="tab-pane">
            <ScenarioResultsView isFixtureMode={isFixtureMode} />
          </div>
        )}
      </main>

      <footer className="cicada-footer">
        <div className="footer-left">
          <span>Cicada Observability SaaS v1.0.0</span>
          <span>&bull;</span>
          <span>Scope: {apiClient.getTenantId()}</span>
        </div>
        <div className="footer-right">
          <span>Prototype</span>
          <span>&bull;</span>
          <span>Separate Local Audit: <code>http://localhost:9001/audit</code></span>
        </div>
      </footer>

      {/* Operator Settings & Scope Modal */}
      <OperatorSettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        onSave={onCredentialsChanged}
      />
    </div>
  );
}

export default App;
