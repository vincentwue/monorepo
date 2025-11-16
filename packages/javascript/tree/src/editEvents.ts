const listeners = new Set<(editingId: string | null) => void>();

export const subscribeEditSession = (listener: (editingId: string | null) => void) => {
  listeners.add(listener);
  return () => void listeners.delete(listener);
};

export const startEditSession = (id: string) => {
  listeners.forEach((fn) => fn(id));
};

export const endEditSession = () => {
  listeners.forEach((fn) => fn(null));
};
