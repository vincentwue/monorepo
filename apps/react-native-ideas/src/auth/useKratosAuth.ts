import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  KratosSession,
  createNativeLoginFlow,
  describeFollowUp,
  fetchSessionViaToken,
  formatTimestamp,
  getEnv,
  sanitizeUrl,
  submitNativeLoginFlow,
  revokeSessionToken,
} from './kratosClient';
import { tokenStorage } from './tokenStorage';

export interface UseKratosAuthResult {
  session: KratosSession | null;
  bootstrapping: boolean;
  statusMessage: string | null;
  error: string | null;
  isBusy: boolean;
  environment: {
    ready: boolean;
    oryBaseUrl: string;
    authUiBaseUrl: string;
    helperText: string;
    errorMessage: string | null;
  };
  signIn: (params: { identifier: string; password: string }) => Promise<void>;
  signOut: () => Promise<void>;
  clearError: () => void;
}

export const useKratosAuth = (): UseKratosAuthResult => {
  const oryBaseUrl = useMemo(
    () =>
      sanitizeUrl(
        getEnv('EXPO_PUBLIC_KRATOS_PUBLIC_URL') ??
          getEnv('EXPO_PUBLIC_ORY_PUBLIC_API_URL') ??
          getEnv('VITE_ORY_PUBLIC_API_URL') ??
          getEnv('KRATOS_PUBLIC_URL') ??
          '',
      ),
    [],
  );
  const authUiBaseUrl = useMemo(
    () =>
      sanitizeUrl(
        getEnv('EXPO_PUBLIC_AUTH_UI_BASE_URL') ??
          getEnv('VITE_AUTH_UI_BASE_URL') ??
          getEnv('AUTH_UI_BASE_URL') ??
          '',
      ),
    [],
  );
  const environmentReady = Boolean(oryBaseUrl);

  const [session, setSession] = useState<KratosSession | null>(null);
  const [sessionToken, setSessionToken] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [bootstrapping, setBootstrapping] = useState(true);
  const [isBusy, setIsBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;

    const loadExistingSession = async () => {
      if (!oryBaseUrl) {
        setBootstrapping(false);
        return;
      }

      try {
        const stored = await tokenStorage.get();
        if (!stored) {
          return;
        }

        const existing = await fetchSessionViaToken(oryBaseUrl, stored);
        if (!cancelled) {
          setSession(existing);
          setSessionToken(stored);
          setStatusMessage('Restored your Kratos session.');
        }
      } catch (err) {
        await tokenStorage.delete().catch(() => undefined);
        if (!cancelled) {
          setSession(null);
          setSessionToken(null);
        }
        console.warn('Unable to resume Kratos session', err);
      } finally {
        if (!cancelled) {
          setBootstrapping(false);
        }
      }
    };

    loadExistingSession();

    return () => {
      cancelled = true;
    };
  }, [oryBaseUrl]);

  const helperText = useMemo(() => {
    if (!environmentReady) {
      return 'Set EXPO_PUBLIC_KRATOS_PUBLIC_URL or update app.config.js to point at your Kratos instance.';
    }
    if (authUiBaseUrl) {
      return `Native login via ${oryBaseUrl}. Portal: ${authUiBaseUrl}`;
    }
    return `Native login via ${oryBaseUrl}`;
  }, [authUiBaseUrl, environmentReady, oryBaseUrl]);

  const environmentError = useMemo(
    () =>
      environmentReady
        ? null
        : 'Kratos base URL missing. Update app.config.js or set EXPO_PUBLIC_KRATOS_PUBLIC_URL.',
    [environmentReady],
  );

  const signIn = useCallback(
    async ({ identifier, password }: { identifier: string; password: string }) => {
      if (!environmentReady || !oryBaseUrl) {
        setError('Kratos base URL is not configured.');
        return;
      }

      if (!identifier.trim() || !password.trim()) {
        setError('Please provide both email and password.');
        return;
      }

      setError(null);
      setStatusMessage(null);
      setIsBusy(true);

      try {
        const flow = await createNativeLoginFlow(oryBaseUrl);
        const result = await submitNativeLoginFlow(oryBaseUrl, flow.id, identifier.trim(), password);

        if (!result.session_token) {
          throw new Error('Kratos did not return a session token.');
        }

        await tokenStorage.set(result.session_token);
        setSessionToken(result.session_token);
        setSession(result.session);
        setStatusMessage(
          describeFollowUp(result.continue_with) ||
            `Authenticated at ${formatTimestamp(result.session?.authenticated_at)}`,
        );
      } catch (err) {
        setSession(null);
        setSessionToken(null);
        setStatusMessage(null);
        setError(err instanceof Error ? err.message : 'Unable to sign in with Kratos.');
      } finally {
        setIsBusy(false);
      }
    },
    [environmentReady, oryBaseUrl],
  );

  const signOut = useCallback(async () => {
    if (!sessionToken || !oryBaseUrl) {
      setSession(null);
      setSessionToken(null);
      setStatusMessage(null);
      await tokenStorage.delete().catch(() => undefined);
      return;
    }

    setIsBusy(true);
    setError(null);
    setStatusMessage(null);

    try {
      await revokeSessionToken(oryBaseUrl, sessionToken);
    } catch (err) {
      console.warn('Failed to revoke Kratos session', err);
    } finally {
      await tokenStorage.delete().catch(() => undefined);
      setSession(null);
      setSessionToken(null);
      setIsBusy(false);
    }
  }, [oryBaseUrl, sessionToken]);

  return {
    session,
    bootstrapping,
    statusMessage,
    error,
    isBusy,
    environment: {
      ready: environmentReady,
      oryBaseUrl,
      authUiBaseUrl,
      helperText,
      errorMessage: environmentError,
    },
    signIn,
    signOut,
    clearError: () => setError(null),
  };
};
