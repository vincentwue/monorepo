import { BaseNode, buildNodeTree } from "./internal/buildNodeTree";
import {
  computeMiddleRank,
  computeRankAfter,
  computeRankBefore,
} from "./internal/rankUtils";
import type { TreeInlineCreateState, TreeState } from "./types";

const RANK_STEP = 100;

const nowIso = (): string => new Date().toISOString();

const normalizeParentId = (value: string | null | undefined): string | null =>
  value ?? null;

const cloneNodes = <T extends BaseNode>(nodes: T[]): T[] =>
  nodes.map((node) => ({ ...node }));

const rebuildState = <T extends BaseNode>(
  nodes: T[],
  expandedIds: string[],
  selectedId: string | null,
  inlineCreate: TreeInlineCreateState | null
): TreeState => {
  const tree = buildNodeTree(nodes);
  return {
    nodes,
    tree: tree.roots,
    flat: tree.flat,
    expandedIds: [...expandedIds],
    selectedId,
    inlineCreate,
  };
};

const reassignRanks = <T extends BaseNode>(
  siblings: T[]
): Map<string, number> => {
  const rankMap = new Map<string, number>();
  siblings.forEach((sibling, index) => {
    rankMap.set(sibling._id ?? "", (index + 1) * RANK_STEP);
  });
  return rankMap;
};

export const indentNode = (
  state: TreeState,
  nodeId: string
): TreeState | null => {
  const target = state.nodes.find((node) => node._id === nodeId);
  if (!target) return null;

  const siblings = state.nodes
    .filter(
      (node) =>
        normalizeParentId(node.parent_id) ===
        normalizeParentId(target.parent_id)
    )
    .slice()
    .sort((a, b) => (a.rank ?? 0) - (b.rank ?? 0));

  const index = siblings.findIndex((node) => node._id === nodeId);
  const prevSibling = index > 0 ? siblings[index - 1] : null;
  if (!prevSibling || !prevSibling._id) return null;

  const cloned = cloneNodes(state.nodes);
  const nodeIndex = cloned.findIndex((node) => node._id === nodeId);
  if (nodeIndex === -1) return null;

  const previousChildren = cloned
    .filter((node) => normalizeParentId(node.parent_id) === prevSibling._id)
    .sort((a, b) => (a.rank ?? 0) - (b.rank ?? 0));

  const lastChild = previousChildren[previousChildren.length - 1] ?? null;
  const nextRank = lastChild ? (lastChild.rank ?? 0) + RANK_STEP : RANK_STEP;

  cloned[nodeIndex] = {
    ...cloned[nodeIndex],
    parent_id: prevSibling._id,
    rank: nextRank,
    updated_at: nowIso(),
  };

  const expandedIds = state.expandedIds.includes(prevSibling._id)
    ? state.expandedIds
    : [...state.expandedIds, prevSibling._id];

  return rebuildState(cloned, expandedIds, nodeId, state.inlineCreate);
};

export const outdentNode = (
  state: TreeState,
  nodeId: string
): TreeState | null => {
  const target = state.nodes.find((node) => node._id === nodeId);
  if (!target || !target.parent_id) return null;

  const parent = state.nodes.find((node) => node._id === target.parent_id);
  if (!parent) return null;

  const grandParentId = normalizeParentId(parent.parent_id);
  const cloned = cloneNodes(state.nodes);
  const nodeIndex = cloned.findIndex((node) => node._id === nodeId);
  if (nodeIndex === -1) return null;

  cloned[nodeIndex] = {
    ...cloned[nodeIndex],
    parent_id: grandParentId,
    updated_at: nowIso(),
  };

  const siblings = cloned
    .filter((node) => normalizeParentId(node.parent_id) === grandParentId)
    .filter((node) => node._id !== nodeId)
    .sort((a, b) => (a.rank ?? 0) - (b.rank ?? 0));

  const insertionIndex = parent._id
    ? siblings.findIndex((node) => node._id === parent._id) + 1
    : siblings.length;

  const orderedSiblings = [...siblings];
  orderedSiblings.splice(insertionIndex, 0, cloned[nodeIndex]);

  const rankAssignments = reassignRanks(orderedSiblings);

  const updatedNodes = cloned.map((node) => {
    const rank = rankAssignments.get(node._id ?? "");
    return rank === undefined
      ? node
      : {
          ...node,
          rank,
          updated_at: node._id === nodeId ? nowIso() : node.updated_at,
        };
  });

  const expandedIds = state.expandedIds.includes(parent._id ?? "")
    ? state.expandedIds
    : parent._id
      ? [...state.expandedIds, parent._id]
      : state.expandedIds;

  return rebuildState(updatedNodes, expandedIds, nodeId, state.inlineCreate);
};

const clampIndex = (index: number, length: number) =>
  Math.max(0, Math.min(length - 1, index));

export const moveNode = (
  state: TreeState,
  nodeId: string,
  delta: number
): TreeState | null => {
  const target = state.nodes.find((node) => node._id === nodeId);
  if (!target) return null;

  const parentId = normalizeParentId(target.parent_id);
  const siblings = state.nodes
    .filter((node) => normalizeParentId(node.parent_id) === parentId)
    .slice()
    .sort((a, b) => (a.rank ?? 0) - (b.rank ?? 0));

  const fromIndex = siblings.findIndex((node) => node._id === nodeId);
  if (fromIndex === -1) return null;

  const toIndex = clampIndex(fromIndex + delta, siblings.length);
  if (toIndex === fromIndex) return null;

  const ordered = [...siblings];
  const [moved] = ordered.splice(fromIndex, 1);
  ordered.splice(toIndex, 0, moved);

  const rankAssignments = reassignRanks(ordered);
  const updatedNodes = state.nodes.map((node) => {
    const rank = rankAssignments.get(node._id ?? "");
    return rank === undefined
      ? node
      : {
          ...node,
          rank,
          updated_at: node._id === nodeId ? nowIso() : node.updated_at,
        };
  });

  return rebuildState(
    updatedNodes,
    state.expandedIds,
    nodeId,
    state.inlineCreate
  );
};

export const updateNodeTitle = (
  state: TreeState,
  params: { id: string; title: string }
): TreeState | null => {
  const index = state.nodes.findIndex((node) => node._id === params.id);
  if (index === -1) return null;

  const cloned = cloneNodes(state.nodes);
  cloned[index] = {
    ...cloned[index],
    title: params.title,
    updated_at: nowIso(),
  };

  return rebuildState(
    cloned,
    state.expandedIds,
    state.selectedId,
    state.inlineCreate
  );
};

export const deleteNode = (state: TreeState, id: string): TreeState | null => {
  const target = state.nodes.find((node) => node._id === id);
  if (!target) return null;

  const collectSubtree = (
    rootId: string,
    nodes: BaseNode[],
    acc: Set<string>
  ) => {
    acc.add(rootId);
    nodes
      .filter((node) => node.parent_id === rootId)
      .forEach((child) => child._id && collectSubtree(child._id, nodes, acc));
  };

  const removedIds = new Set<string>();
  if (target._id) collectSubtree(target._id, state.nodes, removedIds);

  const parentId = normalizeParentId(target.parent_id);
  const siblings = state.nodes
    .filter((node) => normalizeParentId(node.parent_id) === parentId)
    .sort((a, b) => (a.rank ?? 0) - (b.rank ?? 0));

  const currentIndex = siblings.findIndex((node) => node._id === id);
  const nextSibling = siblings[currentIndex + 1] ?? null;
  const prevSibling = siblings[currentIndex - 1] ?? null;

  let nextSelectedId: string | null = null;
  if (nextSibling?._id) nextSelectedId = nextSibling._id;
  else if (prevSibling?._id) nextSelectedId = prevSibling._id;
  else if (parentId) nextSelectedId = parentId;

  const remainingNodes = state.nodes
    .filter((node) => !removedIds.has(node._id ?? ""))
    .map((node) => ({ ...node }));

  const remainingExpandedIds = state.expandedIds.filter(
    (v) => !removedIds.has(v)
  );

  const inlineCreate =
    state.inlineCreate && removedIds.has(state.inlineCreate.tempId)
      ? null
      : state.inlineCreate;

  return rebuildState(
    remainingNodes,
    remainingExpandedIds,
    nextSelectedId,
    inlineCreate
  );
};

/* ────────────────────────────────
   Inline create helpers
──────────────────────────────── */

export const beginInlineCreate = (
  state: TreeState,
  params: {
    tempId: string;
    sourceId: string;
    afterId?: string | null;
    parentId?: string | null;
  }
): TreeState | null => {
  const sourceNode = state.nodes.find((n) => n._id === params.sourceId);
  if (!sourceNode) return null;

  const normalize = (v: string | null | undefined) => v ?? null;
  const desiredParent = normalize(params.parentId ?? sourceNode.parent_id);

  const siblings = state.nodes
    .filter((n) => normalize(n.parent_id) === desiredParent)
    .slice()
    .sort((a, b) => (a.rank ?? 0) - (b.rank ?? 0));

  const index = siblings.findIndex((s) => s._id === sourceNode._id);
  const derivedAfterId =
    params.afterId !== undefined
      ? (params.afterId ?? null)
      : index >= 0
        ? (siblings[index]?._id ?? null)
        : null;

  const inlineCreate: TreeInlineCreateState = {
    tempId: params.tempId,
    afterId: derivedAfterId,
    parentId: desiredParent,
    previousSelectedId: state.selectedId ?? null,
    sourceId: params.sourceId,
  };

  return { ...state, inlineCreate };
};

export const addInlineCreatePlaceholder = (
  state: TreeState,
  payload: { afterId: string | null; node: BaseNode }
): TreeState => {
  const cloned = state.nodes.map((n) => ({ ...n }));

  // remove existing placeholder
  if (payload.node._id) {
    const existingIndex = cloned.findIndex((n) => n._id === payload.node._id);
    if (existingIndex !== -1) cloned.splice(existingIndex, 1);
  }

  const afterNodeIndex = payload.afterId
    ? cloned.findIndex((n) => n._id === payload.afterId)
    : -1;

  const afterNode = afterNodeIndex >= 0 ? cloned[afterNodeIndex] : null;
  const parentId = afterNode?.parent_id ?? payload.node.parent_id ?? null;
  const timestamp = new Date().toISOString();

  const placeholder: BaseNode = {
    ...payload.node,
    parent_id: parentId,
    isPlaceholder: true,
    created_at: payload.node.created_at ?? timestamp,
    updated_at: timestamp,
  };

  if (afterNodeIndex >= 0) cloned.splice(afterNodeIndex + 1, 0, placeholder);
  else cloned.push(placeholder);

  const siblings = cloned
    .filter((n) => n.parent_id === parentId)
    .slice()
    .sort((a, b) => (a.rank ?? 0) - (b.rank ?? 0));

  const idx = siblings.findIndex((n) => n._id === placeholder._id);
  const after = idx > 0 ? siblings[idx - 1] : null;
  const before = idx + 1 < siblings.length ? siblings[idx + 1] : null;

  let nextRank: number;
  if (after && before)
    nextRank = computeMiddleRank(after.rank ?? 0, before.rank ?? 0);
  else if (after) nextRank = computeRankAfter(after.rank ?? 0);
  else if (before) nextRank = computeRankBefore(before.rank ?? 0);
  else nextRank = 100;

  const updated = cloned.map((n) =>
    n._id === placeholder._id ? { ...n, rank: nextRank } : n
  );

  return rebuildState(
    updated,
    state.expandedIds,
    placeholder._id,
    state.inlineCreate
  );
};

export const cancelInlineCreate = (
  state: TreeState,
  tempId: string
): TreeState => {
  const filtered = state.nodes.filter((n) => n._id !== tempId);
  const nextSelection =
    state.inlineCreate?.previousSelectedId ??
    state.inlineCreate?.afterId ??
    state.selectedId ??
    null;

  return rebuildState(filtered, state.expandedIds, nextSelection, null);
};

export const confirmInlineCreate = (
  state: TreeState,
  params: { tempId: string; nodeId?: string | null }
): TreeState | null => {
  const finalId = params.nodeId ?? params.tempId;
  const cloned = state.nodes.map((n) => ({ ...n }));

  const index = cloned.findIndex((n) => n._id === params.tempId);
  if (index === -1) return null;

  cloned[index] = {
    ...cloned[index],
    _id: finalId,
    isPlaceholder: false,
    updated_at: new Date().toISOString(),
  };

  // ensure uniqueness
  const unique = new Map<string, BaseNode>();
  cloned.forEach((n) => unique.set(n._id, n));
  const nodes = Array.from(unique.values());

  return rebuildState(nodes, state.expandedIds, finalId, null);
};
