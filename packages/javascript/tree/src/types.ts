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
  // basic reducer actions
  setNodes: (nodes: BaseNode[]) => void;
  select: (id: string | null) => void;
  toggleExpanded: (id: string) => void;
  setExpanded: (ids: string[]) => void;
  setInlineCreate: (inlineCreate: TreeInlineCreateState | null) => void;

  // extended mutation helpers
  indent: (id: string) => void;
  outdent: (id: string) => void;
  moveUp: (id: string) => void;
  moveDown: (id: string) => void;
  rename: (id: string, title: string) => void;
  delete: (id: string) => void;

  beginInlineCreate: (params: any) => void;
  addInlineCreatePlaceholder: (payload: any) => void;
  cancelInlineCreate: (tempId: string) => void;
  confirmInlineCreate: (params: any) => void;
}

export interface TreePersistence {
  onSelectionChange?: (selectedId: string | null) => void;
  onExpandedChange?: (expandedIds: string[]) => void;
}
