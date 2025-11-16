import type { ReorderDirection } from "@ideas/tree-client";

type TreeStateNode = {
  _id: string;
  parent_id: string | null;
  rank: number;
  title?: string | null;
  isPlaceholder?: boolean;
  updated_at?: string;
};

/**
 * A single mutation inferred from comparing previous and current tree state.
 */
export type TreeMutation =
  | { type: "move"; nodeId: string; newParentId: string | null }
  | { type: "reorder"; nodeId: string; direction: ReorderDirection; targetIndex: number }
  | { type: "rename"; nodeId: string; title: string }
  | { type: "delete"; nodeId: string };

/**
 * Best-effort detection of a single mutation between prev and next tree state.
 * We assume the tree library only applies one logical change at a time
 * (move, reorder, delete) as a result of user interaction.
 */
export function detectTreeMutation(
  prevNodes: TreeStateNode[],
  nextNodes: TreeStateNode[]
): TreeMutation | null {
  const prevById = new Map(prevNodes.map((n) => [n._id, n] as const));
  const nextById = new Map(nextNodes.map((n) => [n._id, n] as const));

  // 1) Detect delete: node present before, missing now.
  for (const [id] of prevById) {
    if (!nextById.has(id)) {
      return { type: "delete", nodeId: id };
    }
  }

  // 2) Detect move: same id, parent changed.
  for (const [id, next] of nextById) {
    const prev = prevById.get(id);
    if (!prev) continue;
    const prevParent = prev.parent_id ?? null;
    const nextParent = next.parent_id ?? null;
    if (prevParent !== nextParent) {
      return { type: "move", nodeId: id, newParentId: nextParent };
    }
  }

  // 3) Detect reorder: parent same, rank changed.
  type ReorderCandidate = {
    nodeId: string;
    direction: ReorderDirection;
    targetIndex: number;
    priority: number;
    delta: number;
  };
  const buildSiblingMap = (nodes: TreeStateNode[]) => {
    const map = new Map<string | null, TreeStateNode[]>();
    for (const node of nodes) {
      const key = node.parent_id ?? null;
      const current = map.get(key);
      if (current) current.push(node);
      else map.set(key, [node]);
    }
    for (const [, siblings] of map) {
      siblings.sort((a, b) => (a.rank ?? 0) - (b.rank ?? 0));
    }
    return map;
  };
  const prevSiblingMap = buildSiblingMap(prevNodes);
  const nextSiblingMap = buildSiblingMap(nextNodes);

  let bestReorder: ReorderCandidate | null = null;
  for (const [id, next] of nextById) {
    const prev = prevById.get(id);
    if (!prev) continue;
    const prevParent = prev.parent_id ?? null;
    const nextParent = next.parent_id ?? null;
    if (prevParent !== nextParent) continue;

    const prevSiblings = prevSiblingMap.get(prevParent);
    const nextSiblings = nextSiblingMap.get(nextParent);
    if (!prevSiblings || !nextSiblings) continue;

    const prevIndex = prevSiblings.findIndex((node) => node._id === id);
    const nextIndex = nextSiblings.findIndex((node) => node._id === id);
    if (prevIndex === -1 || nextIndex === -1) continue;
    if (prevIndex === nextIndex) continue;

    const direction: ReorderDirection = nextIndex < prevIndex ? "up" : "down";
    const delta = Math.abs(nextIndex - prevIndex);
    const priority = prev.updated_at !== next.updated_at ? 2 : 1;

    const candidate: ReorderCandidate = {
      nodeId: id,
      direction,
      targetIndex: nextIndex,
      priority,
      delta,
    };

    if (
      !bestReorder ||
      candidate.priority > bestReorder.priority ||
      (candidate.priority === bestReorder.priority && candidate.delta > bestReorder.delta)
    ) {
      bestReorder = candidate;
    }
  }

  if (bestReorder) {
    return {
      type: "reorder",
      nodeId: bestReorder.nodeId,
      direction: bestReorder.direction,
      targetIndex: bestReorder.targetIndex,
    };
  }

  // 4) Detect rename (title change) on the same node.
  for (const [id, next] of nextById) {
    const prev = prevById.get(id);
    if (!prev) continue;
    if (prev.isPlaceholder || next.isPlaceholder) continue;
    const prevTitle = typeof prev.title === "string" ? prev.title : "";
    const nextTitle = typeof next.title === "string" ? next.title : "";
    if (prevTitle !== nextTitle) {
      return { type: "rename", nodeId: id, title: nextTitle };
    }
  }

  return null;
}
