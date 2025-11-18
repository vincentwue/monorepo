export type KratosMessage = { id: string | number; text?: string };
export type KratosNode = { messages?: KratosMessage[] };

export type KratosLoginFlow = {
  id: string;
  ui?: {
    messages?: KratosMessage[];
    nodes?: KratosNode[];
  };
};

export type KratosIdentity = {
  id?: string;
  traits?: {
    email?: string;
    [key: string]: unknown;
  };
};

export type KratosSession = {
  id: string;
  active?: boolean;
  identity?: KratosIdentity;
  authenticated_at?: string;
  expires_at?: string;
  [key: string]: unknown;
};

export type ContinueWithAction = {
  action: string;
  [key: string]: any;
};

export type KratosLoginResponse = {
  session: KratosSession;
  session_token?: string;
  continue_with?: ContinueWithAction[];
};

export const sanitizeUrl = (value?: string | null) => {
  if (!value) return '';
  return value.replace(/\/$/, '');
};

export const getEnv = (key: string): string | undefined => {
  if (typeof process === 'undefined') return undefined;
  return process.env?.[key];
};

export const formatTimestamp = (value?: string) => {
  if (!value) return 'Pending';
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
};

export const describeFollowUp = (actions?: ContinueWithAction[] | null): string | null => {
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
};

export async function createNativeLoginFlow(baseUrl: string): Promise<KratosLoginFlow> {
  return requestJson(`${baseUrl}/self-service/login/api`, { method: 'GET' });
}

export async function submitNativeLoginFlow(
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

export async function fetchSessionViaToken(baseUrl: string, token: string): Promise<KratosSession> {
  return requestJson(`${baseUrl}/sessions/whoami`, {
    method: 'GET',
    headers: {
      'X-Session-Token': token,
    },
  });
}

export async function revokeSessionToken(baseUrl: string, token: string): Promise<void> {
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

  const response = await fetch(url, {
    ...init,
    headers,
  });

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
