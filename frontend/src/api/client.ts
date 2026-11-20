/**
 * Cicada SaaS Dashboard API Client
 * Strictly follows .planning/CONTRACTS.md.
 * 
 * Rules:
 * - 2-second polling with AbortController cancellation of overlapping requests.
 * - Honest error & disconnect states; NEVER silently substitute mocks on error.
 * - Tenant isolation headers (X-Tenant-ID, Authorization).
 * - Tenant credential change resets cached state and render deduplication keys.
 * - Instrumentation for first-visible-render timing benchmark (deduplicated).
 */

import type {
  ApiClientConfig,
  FleetResponse,
  PayloadDetail,
  TransitionsResponse,
  IncidentSummary,
  IncidentDetail,
  ActionProposal,
  BenchmarkRenderPayload,
  BenchmarkRenderResponse,
  ScenarioResult,
} from '../types/contracts';

export class ApiError extends Error {
  public status: number;
  public statusText: string;
  public endpoint: string;

  constructor(
    status: number,
    statusText: string,
    endpoint: string,
    message?: string,
  ) {
    super(message || `API Error ${status} (${statusText}) on ${endpoint}`);
    this.name = 'ApiError';
    this.status = status;
    this.statusText = statusText;
    this.endpoint = endpoint;
  }
}

export class CicadaApiClient {
  private config: ApiClientConfig;
  private renderedPayloadKeys = new Set<string>();
  private activeControllers = new Map<string, AbortController>();
  public sessionId: string;

  constructor(initialConfig?: Partial<ApiClientConfig>) {
    this.config = {
      baseUrl: initialConfig?.baseUrl || (typeof window !== 'undefined' ? (window as unknown as { __VITE_API_BASE__?: string }).__VITE_API_BASE__ || '' : ''),
      tenantId: initialConfig?.tenantId || 'tenant-alpha',
      operatorToken: initialConfig?.operatorToken || '',
    };
    this.sessionId = `session-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
  }

  /**
   * Reset tenant credentials and wipe deduplication caches
   */
  public setTenant(tenantId: string, operatorToken?: string): void {
    this.config.tenantId = tenantId;
    if (operatorToken !== undefined) {
      this.config.operatorToken = operatorToken;
    }
    this.renderedPayloadKeys.clear();
    this.abortAllRequests();
  }

  public setConfig(newConfig: Partial<ApiClientConfig>): void {
    if (newConfig.baseUrl !== undefined) this.config.baseUrl = newConfig.baseUrl;
    if (newConfig.tenantId !== undefined) this.config.tenantId = newConfig.tenantId;
    if (newConfig.operatorToken !== undefined) this.config.operatorToken = newConfig.operatorToken;
    this.renderedPayloadKeys.clear();
    this.abortAllRequests();
  }

  public getConfig(): ApiClientConfig {
    return { ...this.config };
  }

  public getTenantId(): string {
    return this.config.tenantId;
  }

  public getBaseUrl(): string {
    return this.config.baseUrl;
  }

  public getRenderedCount(): number {
    return this.renderedPayloadKeys.size;
  }

  public clearRenderCache(): void {
    this.renderedPayloadKeys.clear();
  }

  public abortAllRequests(): void {
    for (const [key, controller] of this.activeControllers.entries()) {
      controller.abort();
      this.activeControllers.delete(key);
    }
  }

  /**
   * Internal fetch with AbortController cancellation for overlapping key requests
   */
  private async request<T>(
    endpoint: string,
    options: RequestInit = {},
    cancelKey?: string,
  ): Promise<T> {
    const key = cancelKey || endpoint;

    // Abort preceding in-flight request on the same key to avoid out-of-order race conditions
    if (this.activeControllers.has(key)) {
      this.activeControllers.get(key)!.abort();
      this.activeControllers.delete(key);
    }

    const controller = new AbortController();
    this.activeControllers.set(key, controller);

    const headers: Record<string, string> = {
      'Accept': 'application/json',
      'X-Tenant-ID': this.config.tenantId,
      ...(this.config.operatorToken ? { 'Authorization': `Bearer ${this.config.operatorToken}` } : {}),
      ...(options.headers as Record<string, string> || {}),
    };

    if (options.body && typeof options.body === 'string') {
      headers['Content-Type'] = 'application/json';
    }

    try {
      const response = await fetch(`${this.config.baseUrl}${endpoint}`, {
        ...options,
        headers,
        signal: controller.signal,
      });

      if (!response.ok) {
        throw new ApiError(response.status, response.statusText, endpoint);
      }

      return (await response.json()) as T;
    } catch (err: unknown) {
      if (err instanceof Error && err.name === 'AbortError') {
        throw err; // Propagate aborts naturally
      }
      if (err instanceof ApiError) {
        throw err;
      }
      throw new ApiError(0, 'NETWORK_ERROR', endpoint, (err as Error).message || 'Network connection failed');
    } finally {
      if (this.activeControllers.get(key) === controller) {
        this.activeControllers.delete(key);
      }
    }
  }

  // --- SaaS Operator Endpoints ---

  public async getHealthz(): Promise<{ status: string }> {
    return this.request<{ status: string }>('/healthz', { method: 'GET' }, 'healthz');
  }

  public async getFleet(): Promise<FleetResponse> {
    return this.request<FleetResponse>('/api/v1/fleet', { method: 'GET' }, 'fleet-poll');
  }

  public async getPayload(uuid: string): Promise<PayloadDetail> {
    return this.request<PayloadDetail>(`/api/v1/payloads/${encodeURIComponent(uuid)}`, { method: 'GET' });
  }

  public async getSourceMetrics(
    sourceId: string,
    limit = 50,
    cursor?: string,
  ): Promise<{ items: PayloadDetail[]; next_cursor: string | null }> {
    const params = new URLSearchParams();
    params.set('limit', String(limit));
    if (cursor) params.set('cursor', cursor);
    return this.request<{ items: PayloadDetail[]; next_cursor: string | null }>(
      `/api/v1/sources/${encodeURIComponent(sourceId)}/metrics?${params.toString()}`,
      { method: 'GET' },
      `source-metrics-${sourceId}`,
    );
  }

  public async getTransitions(cursor?: string): Promise<TransitionsResponse> {
    const query = cursor ? `?cursor=${encodeURIComponent(cursor)}` : '';
    return this.request<TransitionsResponse>(`/api/v1/transitions${query}`, { method: 'GET' }, 'transitions');
  }

  public async getIncidents(): Promise<IncidentSummary[]> {
    return this.request<IncidentSummary[]>('/api/v1/incidents', { method: 'GET' }, 'incidents');
  }

  public async getIncident(id: string): Promise<IncidentDetail> {
    return this.request<IncidentDetail>(`/api/v1/incidents/${encodeURIComponent(id)}`, { method: 'GET' });
  }

  public async postProposal(incidentId: string): Promise<ActionProposal> {
    return this.request<ActionProposal>(`/api/v1/incidents/${encodeURIComponent(incidentId)}/proposal`, {
      method: 'POST',
    });
  }

  public async approveRemediation(actionId: string): Promise<ActionProposal> {
    return this.request<ActionProposal>(`/api/v1/remediation/${encodeURIComponent(actionId)}/approve`, {
      method: 'POST',
    });
  }

  public async rollbackRemediation(actionId: string): Promise<ActionProposal> {
    return this.request<ActionProposal>(`/api/v1/remediation/${encodeURIComponent(actionId)}/rollback`, {
      method: 'POST',
    });
  }

  public async getScenarioResults(): Promise<ScenarioResult[]> {
    return this.request<ScenarioResult[]>('/api/v1/scenario-results', { method: 'GET' }, 'scenarios');
  }

  /**
   * First visible render instrumentation.
   * Deduplicates by payload_uuid per session so it is only posted once.
   */
  public async recordFirstRender(payloadUuid: string, runId = 'default-run'): Promise<boolean> {
    if (!payloadUuid || this.renderedPayloadKeys.has(payloadUuid)) {
      return false; // Already submitted once in this session
    }

    this.renderedPayloadKeys.add(payloadUuid);

    const payload: BenchmarkRenderPayload = {
      run_id: runId,
      session_id: this.sessionId,
      payload_uuid: payloadUuid,
      rendered_at_utc: new Date().toISOString(),
    };

    try {
      await this.request<BenchmarkRenderResponse>('/api/v1/benchmarks/render', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      return true;
    } catch {
      // Benchmark timing errors are recorded locally but never break the UI
      return false;
    }
  }
}

// Global singleton instance for UI usage
export const apiClient = new CicadaApiClient();
