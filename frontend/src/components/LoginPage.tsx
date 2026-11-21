import { useRef, useState, type FormEvent } from 'react';
import { ApiError, apiClient, HeimdalApiClient } from '../api/client';
import { FluxLines } from './FluxLines';
import './login.css';

export function LoginPage({ notice, onSuccess }: { notice: string; onSuccess: () => void }) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState(notice);
  const [showToken, setShowToken] = useState(false);
  const tokenField = useRef<HTMLInputElement>(null);

  async function signIn(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) return;
    const fields = new FormData(event.currentTarget);
    const tenantId = String(fields.get('tenant') ?? '').trim();
    const operatorToken = String(fields.get('token') ?? '').trim();
    const baseUrl = String(fields.get('baseUrl') ?? '').trim().replace(/\/+$/, '');
    if (!tenantId || !operatorToken) {
      setError('Enter your tenant ID and operator token.');
      return;
    }

    setError('');
    setPending(true);
    const config = { tenantId, operatorToken, baseUrl };
    try {
      const verifier = new HeimdalApiClient(config);
      await verifier.getFleet();
      apiClient.setConfig(config);
      onSuccess();
    } catch (err) {
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        setError('Sign-in declined. Check that the token belongs to this tenant.');
        tokenField.current?.focus();
      } else {
        setError('Could not connect to the portal. Check the API address and try again.');
      }
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="login-page">
      <div className="login-bg-canvas" aria-hidden="true">
        <FluxLines
          colors={['#38bdf8', '#818cf8', '#c084fc']}
          glow={1.8}
          rimWidth={0.22}
          lineWidth={1}
          speed={0.45}
          flowDirection="down"
          mouseInteraction
          clickSwirl
          transparent
          opacity={0.7}
        />
      </div>
      <div className="login-card">
        <div className="login-banner"><img src="/banner.png" alt="Heimdall" width="1024" height="341" /></div>
        <section className="login-panel" aria-labelledby="login-title">
          <h1 id="login-title">Operator sign-in</h1>
          <p>Enter your tenant credentials to open the operations portal.</p>
          <form onSubmit={signIn} method="post" aria-busy={pending}>
            <label htmlFor="login-tenant">Tenant ID</label>
            <input id="login-tenant" name="tenant" className="input-text mono" required autoComplete="username" readOnly={pending}
              defaultValue={apiClient.getTenantId()} list="login-tenants" spellCheck={false} />
            <datalist id="login-tenants"><option value="tenant-alpha" /><option value="tenant-beta" /></datalist>
            <div className="login-token-label"><label htmlFor="login-token">Operator token</label>
              <button type="button" className="text-btn" aria-controls="login-token" aria-pressed={showToken}
                onClick={() => setShowToken(!showToken)}>{showToken ? 'Hide' : 'Show'}</button></div>
            <input ref={tokenField} id="login-token" name="token" className="input-text mono" type={showToken ? 'text' : 'password'}
              required autoComplete="off" readOnly={pending} spellCheck={false} placeholder="Paste your token" />
            <details className="login-api"><summary>Connection settings</summary>
              <label htmlFor="login-api-url">SaaS API address</label>
              <input id="login-api-url" name="baseUrl" type="url" className="input-text mono" spellCheck={false} readOnly={pending}
                defaultValue={apiClient.getBaseUrl()} placeholder={window.location.origin} />
            </details>
            {error && <p className="connection-error" role="alert">{error}</p>}
            <button type="submit" className="btn-action-primary" disabled={pending}>{pending ? 'Connecting…' : 'Connect dashboard'}</button>
          </form>
        </section>
      </div>
    </main>
  );
}
