import { CollectorLink } from './components/CollectorLink';
import { useWorkspaceMotion } from './hooks/useWorkspaceMotion';
import { useCallback, useEffect, useRef, useState } from 'react';
import { useFleetPolling } from './hooks/useFleetPolling';
import { ConnectionBanner } from './components/ConnectionBanner';
import { BufferStatusCard } from './components/BufferStatusCard';
import { FleetOverview } from './components/FleetOverview';
import { PayloadInspector } from './components/PayloadInspector';
import { TransitionsView } from './components/TransitionsView';
import { IncidentDetailView } from './components/IncidentDetailView';
import { ScenarioResultsView } from './components/ScenarioResultsView';
import { LoginPage } from './components/LoginPage';
import { apiClient } from './api/client';
import { BenchmarkPanel } from './components/BenchmarkPanel';
import { DevDashboard } from './components/DevDashboard';

const views = [
  { key: 'fleet', label: 'Fleet overview', name: 'Fleet & Health State', description: 'Collector health, source activity, and the edge outbox.' },
  { key: 'inspector', label: 'Payload inspector', name: 'Payload Egress Inspector', description: 'Trace an approved payload from the collector to its central receipt.' },
  { key: 'incidents', label: 'Incidents', name: 'AIOps Incidents & Remediation', description: 'Investigate correlated alerts and review simulated remediation.' },
  { key: 'scenarios', label: 'Scenario results', name: 'Scenario Verification (1–8)', description: 'Review the evidence recorded by each local verification run.' },
] as const;

type TabKey = 'fleet' | 'inspector' | 'incidents' | 'scenarios';

export function App() {
  const [signedIn, setSignedIn] = useState(false);
  const [loginNotice, setLoginNotice] = useState('');
  const signOut = useCallback((message = '') => {
    apiClient.setTenant(apiClient.getTenantId(), '');
    setLoginNotice(message);
    setSignedIn(false);
  }, []);

  useEffect(() => {
    window.history.replaceState(null, '', signedIn ? '/' : '/login');
    document.title = signedIn ? 'Heimdal | Operations Dashboard' : 'Heimdal | Operator sign-in';
  }, [signedIn]);

  return signedIn
    ? <Dashboard onSignOut={signOut} />
    : <LoginPage notice={loginNotice} onSuccess={() => setSignedIn(true)} />;
}

function Dashboard({ onSignOut }: { onSignOut: (message?: string) => void }) {
  const [standardTab, setStandardTab] = useState<TabKey>('fleet');
  const [devMode, setDevMode] = useState(false);
  const activeTab = devMode ? 'dev' : standardTab;
  const setActiveTab = (key: TabKey) => {
    setDevMode(false);
    setStandardTab(key);
  };
  const workspace = useRef<HTMLElement>(null);
  useWorkspaceMotion(workspace, activeTab);
  const [inspectPayloadUuid, setInspectPayloadUuid] = useState<string | undefined>(undefined);
  const [targetIncidentId, setTargetIncidentId] = useState<string | undefined>(undefined);

  const {
    data,
    isLoading,
    error,
    isFixtureMode,
    lastSyncUtc,
    serverStatus,
    refreshNow,
    setFixtureMode,
  } = useFleetPolling(2000, onSignOut);

  const handleInspectPayload = (uuid: string) => {
    setInspectPayloadUuid(uuid);
    setActiveTab('inspector');
  };

  const handleSelectIncident = (incidentId: string) => {
    setTargetIncidentId(incidentId);
    setActiveTab('incidents');
  };

  const view = devMode
    ? { label: 'Developer dashboard', description: 'Source telemetry, collector outboxes, and the tenant event log.' }
    : views.find((item) => item.key === standardTab)!;
  return (
    <div className="heimdal-app-shell">
      <a className="skip-link" href="#workspace">Skip to workspace</a>
      <aside className="rail">
        <div className="wordmark"><img src="/favicon.svg" alt="" width="34" height="34" /> Heimdal</div>
        <div className="rail-label">Workspace</div>
        <nav className="tab-navigation" role="tablist" aria-label="Dashboard operational views"
          onKeyDown={(event) => {
            const index = views.findIndex((item) => item.key === standardTab);
            const next = event.key === 'Home' ? 0 : event.key === 'End' ? views.length - 1
              : ['ArrowRight', 'ArrowDown'].includes(event.key) ? (index + 1) % views.length
              : ['ArrowLeft', 'ArrowUp'].includes(event.key) ? (index + views.length - 1) % views.length : -1;
            if (next < 0) return;
            event.preventDefault();
            setActiveTab(views[next].key);
            document.getElementById(`tab-${views[next].key}`)?.focus();
          }}>
          {views.map((item) => (
            <button key={item.key} type="button" role="tab" id={`tab-${item.key}`}
              aria-selected={activeTab === item.key} aria-controls={`panel-${item.key}`}
              aria-label={item.name} tabIndex={standardTab === item.key ? 0 : -1}
              className="tab-btn" onClick={() => setActiveTab(item.key)}>
              <span aria-hidden="true" className={`nav-icon icon-${item.key}`} />
              {item.label}
            </button>
          ))}
        </nav>
        <div className="rail-bottom">
          <span className="rail-label">Collector tools</span>
          <CollectorLink page="audit">Local egress proof <span aria-hidden="true">↗</span></CollectorLink>
          <CollectorLink page="scenarios">Scenario runner <span aria-hidden="true">↗</span></CollectorLink>
        </div>
      </aside>
      <div className="workspace">
        <header className="workspace-bar">
          <span>Operations <span className="slash">/</span> <strong>{view.label}</strong></span>
          <div className="workspace-tools">
            <label className="theme-switch">
              <input type="checkbox" role="switch" checked={devMode} onChange={(event) => setDevMode(event.target.checked)} />
              Dev
            </label>
            <label className="theme-switch">
              <input type="checkbox" role="switch" data-theme-switch defaultChecked={document.documentElement.dataset.theme === 'dark'} />
              Dark mode
            </label>
            <span className="session-tenant" title="Signed-in tenant">{apiClient.getTenantId()}</span>
            <button className="action-btn" onClick={() => onSignOut()}>Sign out</button>
          </div>
        </header>
        <main ref={workspace} id="workspace" tabIndex={-1} className="heimdal-main-content">
          <div className="page-title"><h1>{view.label}</h1><p>{view.description}</p></div>
          <ConnectionBanner serverStatus={serverStatus} error={error} lastSyncUtc={lastSyncUtc}
            isFixtureMode={isFixtureMode} onToggleFixtureMode={setFixtureMode} onRefresh={refreshNow}
            isLoading={isLoading} />
          {devMode && <DevDashboard key={String(isFixtureMode)} fleet={data} fixture={isFixtureMode} onInspect={handleInspectPayload} />}
          {activeTab === 'fleet' && (
            <div
              id="panel-fleet"
              role="tabpanel"
              aria-labelledby="tab-fleet"
              tabIndex={0}
              className="tab-pane"
            >
              <BufferStatusCard
                data={data}
              />
              <FleetOverview
                data={data}
                isLoading={isLoading}
                isFixtureMode={isFixtureMode}
                onInspectPayload={handleInspectPayload}
              />
              <TransitionsView key={String(isFixtureMode)} isFixtureMode={isFixtureMode} />
              {!isFixtureMode && <BenchmarkPanel />}
            </div>
          )}

          {activeTab === 'inspector' && (
            <div
              id="panel-inspector"
              role="tabpanel"
              aria-labelledby="tab-inspector"
              tabIndex={0}
              className="tab-pane"
            >
              <PayloadInspector key={String(isFixtureMode)} isFixtureMode={isFixtureMode} initialUuid={inspectPayloadUuid} />
            </div>
          )}

          {activeTab === 'incidents' && (
            <div
              id="panel-incidents"
              role="tabpanel"
              aria-labelledby="tab-incidents"
              tabIndex={0}
              className="tab-pane"
            >
              <IncidentDetailView
                key={String(isFixtureMode)}
                isFixtureMode={isFixtureMode}
                initialIncidentId={targetIncidentId}
                onInspectPayload={handleInspectPayload}
              />
            </div>
          )}

          {activeTab === 'scenarios' && (
            <div
              id="panel-scenarios"
              role="tabpanel"
              aria-labelledby="tab-scenarios"
              tabIndex={0}
              className="tab-pane"
            >
              <ScenarioResultsView
                key={String(isFixtureMode)}
                isFixtureMode={isFixtureMode}
                onInspectPayload={handleInspectPayload}
                onSelectIncident={handleSelectIncident}
              />
            </div>
          )}
        </main>

        <footer className="heimdal-footer">Heimdal Observability <span>Central workspace · Metadata only</span></footer>
      </div>

    </div>
  );
}

export default App;
