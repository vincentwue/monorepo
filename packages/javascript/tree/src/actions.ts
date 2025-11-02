import {
  addInlineCreatePlaceholder,
  beginInlineCreate,
  cancelInlineCreate,
  confirmInlineCreate,
  deleteNode,
  indentNode,
  moveNode,
  outdentNode,
  updateNodeTitle,
} from "./mutations";
import { getRegisteredTree } from "./registry";
import type { TreeInlineCreateState, TreeState } from "./types";

/** Helpers */
const arraysEqual = (a: string[], b: string[]): boolean =>
  a.length === b.length && a.every((v, i) => v === b[i]);

const inlineEqual = (
  a: TreeInlineCreateState | null,
  b: TreeInlineCreateState | null
): boolean => {
  if (a === b) return true;
  if (!a || !b) return false;
  return (
    a.tempId === b.tempId &&
    a.afterId === b.afterId &&
    a.parentId === b.parentId &&
    a.previousSelectedId === b.previousSelectedId &&
    a.sourceId === b.sourceId &&
    a.nodeId === b.nodeId
  );
};

const applyProviderState = (
  registered: ReturnType<typeof getRegisteredTree>,
  next: TreeState
) => {
  if (!registered) return;

  let current = registered.getState();

  if (
    current.nodes !== next.nodes ||
    current.nodes.length !== next.nodes.length
  ) {
    registered.actions.setNodes(next.nodes);
    current = registered.getState();
  }

  if (!arraysEqual(current.expandedIds, next.expandedIds)) {
    registered.actions.setExpanded(next.expandedIds);
    current = registered.getState();
  }

  if (current.selectedId !== next.selectedId) {
    registered.actions.select(next.selectedId ?? null);
    current = registered.getState();
  }

  if (!inlineEqual(current.inlineCreate, next.inlineCreate)) {
    registered.actions.setInlineCreate(next.inlineCreate);
  }
};

/** ────────────────────────────────
 *  Generic Tree Actions
 *  ────────────────────────────────*/

export const setTreeNodes = (key: string, nodes: any[]) => {
  const reg = getRegisteredTree(key);
  if (reg) reg.actions.setNodes(nodes);
};

export const selectTreeNode = (key: string, id: string | null) => {
  const reg = getRegisteredTree(key);
  if (reg) reg.actions.select(id);
};

export const setTreeExpandedIds = (key: string, ids: string[]) => {
  const reg = getRegisteredTree(key);
  if (reg) reg.actions.setExpanded(ids);
};

export const toggleTreeNodeExpanded = (key: string, id: string) => {
  const reg = getRegisteredTree(key);
  if (reg) reg.actions.toggleExpanded(id);
  return Promise.resolve();
};

export const indentTreeNode = (key: string, id: string) => {
  const reg = getRegisteredTree(key);
  if (!reg) return;
  const next = indentNode(reg.getState(), id);
  if (next) applyProviderState(reg, next);
};

export const outdentTreeNode = (key: string, id: string) => {
  const reg = getRegisteredTree(key);
  if (!reg) return;
  const next = outdentNode(reg.getState(), id);
  if (next) applyProviderState(reg, next);
};

export const moveTreeNode = (key: string, id: string, delta: number) => {
  const reg = getRegisteredTree(key);
  if (!reg) return;
  const next = moveNode(reg.getState(), id, delta);
  if (next) applyProviderState(reg, next);
};

export const updateTreeNodeTitle = (key: string, id: string, title: string) => {
  const reg = getRegisteredTree(key);
  if (!reg) return;
  const next = updateNodeTitle(reg.getState(), { id, title });
  if (next) applyProviderState(reg, next);
};

export const beginInlineCreateSession = (
  key: string,
  params: {
    tempId: string;
    sourceId: string;
    afterId?: string | null;
    parentId?: string | null;
  }
) => {
  const reg = getRegisteredTree(key);
  if (!reg) return;
  const next = beginInlineCreate(reg.getState(), params);
  if (next) reg.actions.setInlineCreate(next.inlineCreate);
};

export const addInlineCreatePlaceholderNode = (
  key: string,
  payload: { afterId: string | null; node: any }
) => {
  const reg = getRegisteredTree(key);
  if (!reg) return;
  const next = addInlineCreatePlaceholder(reg.getState(), payload as any);
  applyProviderState(reg, next);
};

export const cancelInlineCreateSession = (key: string, tempId: string) => {
  const reg = getRegisteredTree(key);
  if (!reg) return;
  const next = cancelInlineCreate(reg.getState(), tempId);
  applyProviderState(reg, next);
};

export const confirmInlineCreateSession = (
  key: string,
  payload: { tempId: string; nodeId?: string | null }
) => {
  const reg = getRegisteredTree(key);
  if (!reg) return;
  const next = confirmInlineCreate(reg.getState(), payload);
  if (next) applyProviderState(reg, next);
};

export const deleteTreeNode = (key: string, id: string) => {
  const reg = getRegisteredTree(key);
  if (!reg) return;
  const next = deleteNode(reg.getState(), id);
  if (next) applyProviderState(reg, next);
};
