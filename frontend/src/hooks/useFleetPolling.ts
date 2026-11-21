import { useState, useEffect, useCallback, useRef } from 'react';
import { apiClient, ApiError } from '../api/client';
import type { FleetResponse } from '../types/contracts';
import { MOCK_FLEET_RESPONSE } from '../fixtures/metadataFixtures';

export interface UseFleetPollingResult {
  data: FleetResponse | null;
  isLoading: boolean;
  error: ApiError | null;
  isFixtureMode: boolean;
  lastSyncUtc: string | null;
  serverStatus: 'connected' | 'disconnected' | 'fixture';
  refreshNow: () => Promise<void>;
  setFixtureMode: (enabled: boolean) => void;
}

export function useFleetPolling(pollIntervalMs = 2000, onAccessDenied?: (message: string) => void): UseFleetPollingResult {
  const [data, setData] = useState<FleetResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<ApiError | null>(null);
  const [isFixtureMode, setIsFixtureMode] = useState<boolean>(false);
  const [lastSyncUtc, setLastSyncUtc] = useState<string | null>(null);

  const isMountedRef = useRef(true);

  const fetchFleet = useCallback(async (fixtureFallback = false) => {
    if (fixtureFallback) {
      setData(MOCK_FLEET_RESPONSE);
      setError(null);
      setIsLoading(false);
      setLastSyncUtc(new Date().toISOString());
      return;
    }

    try {
      const response = await apiClient.getFleet();
      if (isMountedRef.current) {
        setData(response);
        setError(null);
        setLastSyncUtc(response.server_time_utc || new Date().toISOString());
        setIsLoading(false);
      }
    } catch (err: unknown) {
      if (isMountedRef.current) {
        if (err instanceof Error && err.name === 'AbortError') {
          return; // Ignore aborted requests
        }
        const apiErr = err instanceof ApiError ? err : new ApiError(0, 'UNKNOWN', '/api/v1/fleet', (err as Error).message);
        if (onAccessDenied && (apiErr.status === 401 || apiErr.status === 403)) {
          onAccessDenied('Your operator credentials are no longer accepted. Sign in again.');
          return;
        }
        setError(apiErr);
        setIsLoading(false);
        // Do NOT silently replace data with mock fixture on error!
      }
    }
  }, [onAccessDenied]);

  useEffect(() => {
    isMountedRef.current = true;

    // Initial fetch
    fetchFleet(isFixtureMode);

    if (isFixtureMode) {
      return () => {
        isMountedRef.current = false;
      };
    }

    const interval = setInterval(() => {
      fetchFleet(false);
    }, pollIntervalMs);

    return () => {
      isMountedRef.current = false;
      clearInterval(interval);
      apiClient.abortAllRequests();
    };
  }, [fetchFleet, isFixtureMode, pollIntervalMs]);

  const refreshNow = useCallback(async () => {
    setIsLoading(true);
    await fetchFleet(isFixtureMode);
  }, [fetchFleet, isFixtureMode]);

  const setFixtureModeHandler = useCallback((enabled: boolean) => {
    setIsFixtureMode(enabled);
    if (enabled) {
      setData(MOCK_FLEET_RESPONSE);
      setError(null);
      setLastSyncUtc(new Date().toISOString());
    } else {
      setData(null);
      setIsLoading(true);
      fetchFleet(false);
    }
  }, [fetchFleet]);

  let serverStatus: 'connected' | 'disconnected' | 'fixture' = 'connected';
  if (isFixtureMode) {
    serverStatus = 'fixture';
  } else if (error) {
    serverStatus = 'disconnected';
  } else if (!data && isLoading) {
    serverStatus = 'disconnected';
  }

  return {
    data,
    isLoading,
    error,
    isFixtureMode,
    lastSyncUtc,
    serverStatus,
    refreshNow,
    setFixtureMode: setFixtureModeHandler,
  };
}
