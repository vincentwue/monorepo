const SESSION_TOKEN_KEY = 'ideas.kratos.session-token';

const getBrowserStore = () => {
  if (typeof window !== 'undefined' && window.localStorage) {
    return window.localStorage;
  }
  return null;
};

let fallbackToken: string | null = null;

export const tokenStorage = {
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
