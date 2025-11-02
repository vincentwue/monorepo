import type { BaseNode, NodeTreeNode } from "./internal/buildNodeTree";

export interface TreeInlineCreateState {
  tempId: string;
  nodeId?: string | null;
  afterId: string | null;
  parentId: string | null;
  previousSelectedId: string | null;
  sourceId: string;
}

export interface TreeState {
  nodes: BaseNode[];
  tree: NodeTreeNode[];
  flat: NodeTreeNode[];
  expandedIds: string[];
  selectedId: string | null;
  inlineCreate: TreeInlineCreateState | null;
}

export interface TreeActions {
  setNodes: (nodes: BaseNode[]) => void;
  select: (id: string | null) => void;
  toggleExpanded: (id: string) => void;
  setExpanded: (ids: string[]) => void;
  setInlineCreate: (inlineCreate: TreeInlineCreateState | null) => void;
}

export interface TreePersistence {
  onSelectionChange?: (selectedId: string | null) => void;
  onExpandedChange?: (expandedIds: string[]) => void;
}
