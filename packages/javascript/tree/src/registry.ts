import type { TreeState, TreeActions } from "./types";

interface RegisteredTree {
  getState: () => TreeState;
  actions: TreeActions;
}

const registry = new Map<string, RegisteredTree>();

export const registerTree = (key: string, descriptor: RegisteredTree) => {
  registry.set(key, descriptor);
};

export const unregisterTree = (key: string) => {
  registry.delete(key);
};

export const getRegisteredTree = (key: string): RegisteredTree | undefined => registry.get(key);

export const listRegisteredTrees = (): string[] => Array.from(registry.keys());

