import type { ReorderDirection } from "@ideas/tree-client";

export type TreeMutation =
  | { type: "move"; nodeId: string; newParentId: string | null }
  | { type: "reorder"; nodeId: string; direction: ReorderDirection };

export interface TreeNodeLike {
  _id?: string;
  parent_id?: string | null;
  rank?: number | null;
  [key: string]: unknown;
}

interface NodeOrderInfo {
  parentId: string | null;
  order: number;
}

const normalizeParentId = (value: string | null | undefined): string | null => value ?? null;

const isPlaceholderNode = (node?: TreeNodeLike): boolean =>
  Boolean(node && (node as Record<string, unknown>).isPlaceholder);

const readUpdatedAt = (node: TreeNodeLike): string | null => {
  const value = (node as Record<string, unknown>).updated_at;
  return typeof value === "string" ? value : null;
};

const buildNodeOrderMap = (nodes: TreeNodeLike[]): Map<string, NodeOrderInfo> => {
  const buckets = new Map<string | null, TreeNodeLike[]>();

  for (const node of nodes) {
    if (!node?._id) continue;
    if (isPlaceholderNode(node)) continue;
    const parentId = normalizeParentId(node.parent_id);
    const list = buckets.get(parentId);
    if (list) list.push(node);
    else buckets.set(parentId, [node]);
  }

  const orderMap = new Map<string, NodeOrderInfo>();
  for (const [parentId, list] of buckets.entries()) {
    list
      .slice()
      .sort((a, b) => {
        const rankA = typeof a.rank === "number" ? a.rank : 0;
        const rankB = typeof b.rank === "number" ? b.rank : 0;
        if (rankA !== rankB) return rankA - rankB;
        return a._id!.localeCompare(b._id!);
      })
      .forEach((node, index) => {
        orderMap.set(node._id!, { parentId, order: index });
      });
  }

  return orderMap;
};

export function detectTreeMutation<TNode extends TreeNodeLike>(
  prevNodes: TNode[],
  nextNodes: TNode[],
): TreeMutation | null {
  if (!prevNodes.length || !nextNodes.length) {
    return null;
  }

  const prevById = new Map(prevNodes.map((node) => [node._id, node]));
  const prevOrderMap = buildNodeOrderMap(prevNodes);
  const nextOrderMap = buildNodeOrderMap(nextNodes);

  type MoveCandidate = { nodeId: string; newParentId: string | null; score: number };
  type ReorderCandidate = { nodeId: string; direction: ReorderDirection; score: number };

  let moveCandidate: MoveCandidate | null = null;
  let reorderCandidate: ReorderCandidate | null = null;

  for (const node of nextNodes) {
    const id = node?._id;
    if (!id) continue;
    if (isPlaceholderNode(node)) continue;

    const prevNode = prevById.get(id);
    if (!prevNode || isPlaceholderNode(prevNode)) continue;

    const prevInfo = prevOrderMap.get(id);
    const nextInfo = nextOrderMap.get(id);
    if (!nextInfo) continue;

    const prevParent = prevInfo?.parentId ?? normalizeParentId(prevNode.parent_id);
    const nextParent = nextInfo.parentId;
    const updated = readUpdatedAt(prevNode) !== readUpdatedAt(node);
    const score = updated ? 2 : 1;

    if (prevParent !== nextParent) {
      const candidate: MoveCandidate = { nodeId: id, newParentId: nextParent, score };
      if (!moveCandidate || candidate.score > moveCandidate.score) {
        moveCandidate = candidate;
      }
      continue;
    }

    if (!prevInfo || prevInfo.order === nextInfo.order) continue;

    const direction: ReorderDirection = nextInfo.order < prevInfo.order ? "up" : "down";
    const candidate: ReorderCandidate = { nodeId: id, direction, score };
    if (!reorderCandidate || candidate.score > reorderCandidate.score) {
      reorderCandidate = candidate;
    }
  }

  if (moveCandidate) {
    return {
      type: "move",
      nodeId: moveCandidate.nodeId,
      newParentId: moveCandidate.newParentId,
    };
  }

  if (reorderCandidate) {
    return {
      type: "reorder",
      nodeId: reorderCandidate.nodeId,
      direction: reorderCandidate.direction,
    };
  }

  return null;
}
