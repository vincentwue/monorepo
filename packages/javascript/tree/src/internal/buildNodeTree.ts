import { buildTree } from "./buildTree";

/**
 * Minimal flat node interface.
 * Works for any structure that has `_id`, `parent_id`, and `rank`.
 */
export interface BaseNode {
  _id: string;
  parent_id: string | null;
  rank?: number;
  title?: string;
  updated_at?: string;
  created_at?: string;
  [key: string]: any;
}

/**
 * Tree node with children and depth.
 */
export interface NodeTreeNode extends BaseNode {
  children: NodeTreeNode[];
  depth: number;
}

export interface NodeTree {
  roots: NodeTreeNode[];
  flat: NodeTreeNode[];
}

interface BuildNodeTreeOptions {
  sort?: boolean;
}

/**
 * Build a hierarchical tree structure from a flat node array.
 */
export function buildNodeTree(
  nodes: BaseNode[],
  opts: BuildNodeTreeOptions = {}
): NodeTree {
  const { sort = true } = opts;

  // Normalize and clone
  const normalized = nodes.map((n) => ({
    ...n,
    _id: n._id ?? `node-${Math.random().toString(36).slice(2)}`,
    parent_id: n.parent_id ?? null,
    rank: n.rank ?? 0,
  }));

  const roots = buildTree<NodeTreeNode>(normalized as any, {
    idKey: "_id",
    parentKey: "parent_id",
    rankKey: "rank",
    sort,
  }) as NodeTreeNode[];

  const assignDepth = (nodes: NodeTreeNode[], depth = 0) => {
    for (const node of nodes) {
      node.depth = depth;
      if (node.children?.length) assignDepth(node.children, depth + 1);
    }
  };

  assignDepth(roots, 0);

  const flatten = (
    nodes: NodeTreeNode[],
    acc: NodeTreeNode[] = []
  ): NodeTreeNode[] => {
    for (const n of nodes) {
      acc.push(n);
      if (n.children?.length) flatten(n.children, acc);
    }
    return acc;
  };

  const flat = flatten(roots);
  return { roots, flat };
}
