import type { ReorderDirection } from "@ideas/tree-client";

type TreeStateNode = {
  _id: string;
  parent_id: string | null;
  rank: number;
};

/**
 * A single mutation inferred from comparing previous and current tree state.
 */
export type TreeMutation =
  | { type: "move"; nodeId: string; newParentId: string | null }
  | { type: "reorder"; nodeId: string; direction: ReorderDirection }
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
  for (const [id, next] of nextById) {
    const prev = prevById.get(id);
    if (!prev) continue;
    if (prev.parent_id !== next.parent_id) continue;

    const prevRank = typeof prev.rank === "number" ? prev.rank : 0;
    const nextRank = typeof next.rank === "number" ? next.rank : 0;

    if (prevRank !== nextRank) {
      const direction: ReorderDirection = nextRank < prevRank ? "up" : "down";
      return { type: "reorder", nodeId: id, direction };
    }
  }

  return null;
}
