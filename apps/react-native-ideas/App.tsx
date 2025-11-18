import { useCallback, useEffect, useMemo, useState } from 'react';
import { StatusBar } from 'expo-status-bar';
import {
  ActivityIndicator,
  Linking,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

type KratosMessage = { id: string | number; text?: string };
type KratosNode = { messages?: KratosMessage[] };

type KratosLoginFlow = {
  id: string;
  ui?: {
    messages?: KratosMessage[];
    nodes?: KratosNode[];
  };
};

type KratosIdentity = {
  id?: string;
  traits?: {
    email?: string;
    [key: string]: unknown;
  };
};

type KratosSession = {
  id: string;
  active?: boolean;
  identity?: KratosIdentity;
  authenticated_at?: string;
  expires_at?: string;
  [key: string]: unknown;
};

type ContinueWithAction = {
  action: string;
  [key: string]: any;
};

type KratosLoginResponse = {
  session: KratosSession;
  session_token?: string;
  continue_with?: ContinueWithAction[];
};

const SESSION_TOKEN_KEY = 'ideas.kratos.session-token';
const tokenStorage = createTokenStorage();

export default function App() {
  const oryBaseUrl = sanitizeUrl(
    getEnv('EXPO_PUBLIC_KRATOS_PUBLIC_URL') ??
      getEnv('EXPO_PUBLIC_ORY_PUBLIC_API_URL') ??
      getEnv('VITE_ORY_PUBLIC_API_URL') ??
      getEnv('KRATOS_PUBLIC_URL') ??
      '',
  );
  const authUiBaseUrl = sanitizeUrl(
    getEnv('EXPO_PUBLIC_AUTH_UI_BASE_URL') ??
      getEnv('VITE_AUTH_UI_BASE_URL') ??
      getEnv('AUTH_UI_BASE_URL') ??
      '',
  );

  const environmentReady = Boolean(oryBaseUrl);

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [session, setSession] = useState<KratosSession | null>(null);
  const [sessionToken, setSessionToken] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [bootstrapping, setBootstrapping] = useState(true);

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

  const formatIdentityLabel = useMemo(() => {
    const identityEmail = session?.identity?.traits?.email;
    if (identityEmail) return identityEmail;
    return session?.identity?.id ?? 'Unknown identity';
  }, [session]);

  const handleLogin = useCallback(async () => {
    if (!environmentReady || !oryBaseUrl) {
      setError('Kratos base URL is not configured.');
      return;
    }

    if (!email.trim() || !password.trim()) {
      setError('Please provide both email and password.');
      return;
    }

    setError(null);
    setStatusMessage(null);
    setIsSubmitting(true);

    try {
      const flow = await createNativeLoginFlow(oryBaseUrl);
      const result = await submitNativeLoginFlow(oryBaseUrl, flow.id, email.trim(), password);

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
      setPassword('');
    } catch (err) {
      setSession(null);
      setSessionToken(null);
      setStatusMessage(null);
      setError(err instanceof Error ? err.message : 'Unable to sign in with Kratos.');
    } finally {
      setIsSubmitting(false);
    }
  }, [email, environmentReady, oryBaseUrl, password]);

  const handleLogout = useCallback(async () => {
    if (!oryBaseUrl) {
      setSession(null);
      setSessionToken(null);
      setStatusMessage(null);
      setPassword('');
      await tokenStorage.delete().catch(() => undefined);
      return;
    }

    if (!sessionToken) {
      setSession(null);
      setStatusMessage(null);
      return;
    }

    setIsSubmitting(true);
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
      setPassword('');
      setIsSubmitting(false);
    }
  }, [oryBaseUrl, sessionToken]);

  const openPortal = useCallback(
    (path: string) => {
      if (!authUiBaseUrl) return;
      const target = `${authUiBaseUrl}${path}`;
      Linking.openURL(target).catch((err) => {
        console.warn('Failed to open auth portal', err);
        setError('Unable to open the browser auth portal.');
      });
    },
    [authUiBaseUrl],
  );

  const renderBootstrapping = () => (
    <View style={styles.card}>
      <Text style={styles.heading}>Connecting to Kratos</Text>
      <Text style={styles.subtitle}>Checking for an existing session...</Text>
      <ActivityIndicator style={styles.bootLoader} color="#7f56d9" />
    </View>
  );

  const renderLogin = () => (
    <View style={styles.card}>
      <Text style={styles.heading}>Sign in with Kratos</Text>
      <Text style={styles.subtitle}>Use your Ory identity credentials.</Text>

      <View style={styles.formGroup}>
        <Text style={styles.label}>Email</Text>
        <TextInput
          autoCapitalize="none"
          autoComplete="email"
          autoCorrect={false}
          keyboardType="email-address"
          placeholder="you@example.com"
          placeholderTextColor="#98a2b3"
          style={styles.input}
          value={email}
          onChangeText={setEmail}
        />
      </View>

      <View style={styles.formGroup}>
        <Text style={styles.label}>Password</Text>
        <TextInput
          autoCapitalize="none"
          placeholder="********"
          placeholderTextColor="#98a2b3"
          secureTextEntry
          style={styles.input}
          value={password}
          onChangeText={setPassword}
        />
      </View>

      <Pressable
        accessibilityRole="button"
        disabled={!environmentReady || isSubmitting}
        onPress={handleLogin}
        style={({ pressed }) => [
          styles.button,
          pressed && styles.buttonPressed,
          (!environmentReady || isSubmitting) && styles.buttonDisabled,
        ]}
      >
        {isSubmitting ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.buttonLabel}>Sign In</Text>
        )}
      </Pressable>

      {statusMessage && (
        <View style={styles.noticeBox}>
          <Text style={styles.noticeText}>{statusMessage}</Text>
        </View>
      )}

      {environmentError && <Text style={styles.errorText}>{environmentError}</Text>}
      {error && <Text style={styles.errorText}>{error}</Text>}
      {!error && !environmentError && <Text style={styles.helperText}>{helperText}</Text>}

      {authUiBaseUrl ? (
        <View style={styles.linksRow}>
          <Pressable
            accessibilityRole="link"
            onPress={() => openPortal('/register')}
            style={styles.textButton}
          >
            <Text style={styles.textButtonLabel}>Register in browser</Text>
          </Pressable>
          <Pressable
            accessibilityRole="link"
            onPress={() => openPortal('/recovery')}
            style={styles.textButton}
          >
            <Text style={styles.textButtonLabel}>Forgot password</Text>
          </Pressable>
        </View>
      ) : null}
    </View>
  );

  const renderWelcome = () => (
    <View style={styles.card}>
      <Text style={styles.heading}>You're signed in</Text>
      <Text style={styles.subtitle}>{formatIdentityLabel}</Text>

      {statusMessage && (
        <View style={styles.noticeBox}>
          <Text style={styles.noticeText}>{statusMessage}</Text>
        </View>
      )}

      <View style={styles.metaContainer}>
        <View style={styles.metaRow}>
          <Text style={styles.metaLabel}>Session</Text>
          <Text style={styles.metaValue}>{session?.id ?? '—'}</Text>
        </View>
        <View style={styles.metaRow}>
          <Text style={styles.metaLabel}>Authenticated</Text>
          <Text style={styles.metaValue}>{formatTimestamp(session?.authenticated_at)}</Text>
        </View>
        <View style={styles.metaRow}>
          <Text style={styles.metaLabel}>Expires</Text>
          <Text style={styles.metaValue}>
            {session?.expires_at ? formatTimestamp(session.expires_at) : 'Configured lifespan'}
          </Text>
        </View>
      </View>

      <Pressable
        accessibilityRole="button"
        onPress={handleLogout}
        style={({ pressed }) => [
          styles.button,
          styles.secondaryButton,
          pressed && styles.secondaryPressed,
        ]}
      >
        {isSubmitting ? (
          <ActivityIndicator color="#7f56d9" />
        ) : (
          <Text style={[styles.buttonLabel, styles.secondaryButtonLabel]}>Log out</Text>
        )}
      </Pressable>

      {error && <Text style={styles.errorText}>{error}</Text>}
      {!error && <Text style={styles.helperText}>{helperText}</Text>}
    </View>
  );

  return (
    <View style={styles.container}>
      <StatusBar style="dark" />
      {bootstrapping ? (
        renderBootstrapping()
      ) : session ? (
        renderWelcome()
      ) : (
        renderLogin()
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f3f3f5',
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 24,
  },
  card: {
    width: '100%',
    maxWidth: 440,
    backgroundColor: '#ffffff',
    borderRadius: 16,
    padding: 24,
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 10 },
    shadowOpacity: 0.1,
    shadowRadius: 20,
    elevation: 6,
  },
  heading: {
    fontSize: 24,
    fontWeight: '600',
    color: '#1d2939',
  },
  subtitle: {
    fontSize: 16,
    color: '#475467',
    marginTop: 4,
    marginBottom: 24,
  },
  formGroup: {
    marginBottom: 16,
  },
  label: {
    fontSize: 14,
    fontWeight: '500',
    marginBottom: 6,
    color: '#475467',
  },
  input: {
    borderWidth: 1,
    borderColor: '#d0d5dd',
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 16,
    color: '#101828',
    backgroundColor: '#f8fafc',
  },
  button: {
    backgroundColor: '#7f56d9',
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: 'center',
    marginTop: 8,
  },
  buttonPressed: {
    opacity: 0.85,
  },
  buttonDisabled: {
    opacity: 0.6,
  },
  buttonLabel: {
    fontSize: 16,
    fontWeight: '600',
    color: '#fff',
  },
  helperText: {
    marginTop: 16,
    color: '#475467',
    textAlign: 'center',
    fontSize: 14,
  },
  errorText: {
    marginTop: 16,
    color: '#d92d20',
    textAlign: 'center',
    fontSize: 14,
  },
  metaContainer: {
    backgroundColor: '#f8f3ff',
    padding: 16,
    borderRadius: 12,
    marginBottom: 24,
    marginTop: 8,
  },
  metaRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 10,
  },
  metaLabel: {
    fontSize: 12,
    color: '#6941c6',
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 0.8,
  },
  metaValue: {
    fontSize: 16,
    color: '#101828',
  },
  secondaryButton: {
    backgroundColor: '#efe9fc',
  },
  secondaryPressed: {
    opacity: 0.6,
  },
  secondaryButtonLabel: {
    color: '#7f56d9',
  },
  noticeBox: {
    backgroundColor: '#efe9fc',
    borderRadius: 10,
    padding: 12,
    marginTop: 16,
    borderWidth: 1,
    borderColor: '#d6bbfb',
  },
  noticeText: {
    color: '#53389e',
    fontSize: 14,
  },
  textButton: {
    paddingVertical: 6,
    paddingHorizontal: 12,
  },
  textButtonLabel: {
    color: '#7f56d9',
    fontSize: 14,
    fontWeight: '500',
  },
  linksRow: {
    marginTop: 16,
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  bootLoader: {
    marginTop: 12,
  },
});

function sanitizeUrl(value?: string | null) {
  if (!value) return '';
  return value.replace(/\/$/, '');
}

function getEnv(key: string): string | undefined {
  if (typeof process === 'undefined') return undefined;
  return process.env?.[key];
}

async function createNativeLoginFlow(baseUrl: string): Promise<KratosLoginFlow> {
  return requestJson(`${baseUrl}/self-service/login/api`, { method: 'GET' });
}

async function submitNativeLoginFlow(
  baseUrl: string,
  flowId: string,
  identifier: string,
  password: string,
): Promise<KratosLoginResponse> {
  return requestJson(`${baseUrl}/self-service/login?flow=${encodeURIComponent(flowId)}`, {
    method: 'POST',
    body: JSON.stringify({
      method: 'password',
      identifier,
      password,
    }),
  });
}

async function fetchSessionViaToken(baseUrl: string, token: string): Promise<KratosSession> {
  return requestJson(`${baseUrl}/sessions/whoami`, {
    method: 'GET',
    headers: {
      'X-Session-Token': token,
    },
  });
}

async function revokeSessionToken(baseUrl: string, token: string): Promise<void> {
  await requestJson(`${baseUrl}/self-service/logout/api`, {
    method: 'DELETE',
    body: JSON.stringify({ session_token: token }),
  });
}

async function requestJson(url: string, init: RequestInit): Promise<any> {
  const headers: Record<string, string> = {
    Accept: 'application/json',
  };

  if (init.headers) {
    Object.assign(headers, init.headers as Record<string, string>);
  }

  if (init.body && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }

  const response = await fetch(
    url,
    {
      ...init,
      headers,
    },
  );

  const rawText = await response.text();
  let data: any = null;
  if (rawText) {
    try {
      data = JSON.parse(rawText);
    } catch {
      data = rawText;
    }
  }

  if (!response.ok) {
    const message =
      extractOryErrorMessage(data) ||
      (typeof data === 'string' ? data : `Request failed (${response.status})`);
    const error = new Error(message);
    (error as any).payload = data;
    throw error;
  }

  return data;
}

function extractOryErrorMessage(payload: any): string | null {
  if (!payload || typeof payload !== 'object') {
    return null;
  }

  if (typeof payload.error === 'string') {
    return payload.error;
  }

  if (payload.error?.message) {
    return payload.error.message;
  }

  if (typeof payload.message === 'string') {
    return payload.message;
  }

  const messages: KratosMessage[] = [
    ...(payload.ui?.messages ?? []),
    ...(payload.messages ?? []),
    ...((payload.ui?.nodes ?? [])
      .flatMap((node: KratosNode) => node.messages ?? [])
      .filter(Boolean) as KratosMessage[]),
  ];

  if (messages.length > 0) {
    return messages[0]?.text ?? null;
  }

  return null;
}

function describeFollowUp(actions?: ContinueWithAction[] | null): string | null {
  if (!actions?.length) return null;
  const labels = actions
    .map((action) => {
      switch (action.action) {
        case 'show_verification_ui':
          return 'Verification required. Check your inbox to finish linking this identity.';
        case 'set_session_token':
          return 'Session token issued.';
        default:
          return `Continue with: ${action.action.replace(/[_-]/g, ' ')}`;
      }
    })
    .filter(Boolean);
  return labels.join('\n');
}

function formatTimestamp(value?: string) {
  if (!value) return 'Pending';
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

function createTokenStorage() {
  let fallbackToken: string | null = null;

  const getBrowserStore = () => {
    if (typeof window !== 'undefined' && window.localStorage) {
      return window.localStorage;
    }
    return null;
  };

  return {
    get: async () => {
      const storage = getBrowserStore();
      if (storage) {
        return storage.getItem(SESSION_TOKEN_KEY);
      }
      return fallbackToken;
    },
    set: async (value: string) => {
      const storage = getBrowserStore();
      if (storage) {
        storage.setItem(SESSION_TOKEN_KEY, value);
      } else {
        fallbackToken = value;
      }
    },
    delete: async () => {
      const storage = getBrowserStore();
      if (storage) {
        storage.removeItem(SESSION_TOKEN_KEY);
      } else {
        fallbackToken = null;
      }
    },
  };
}
