import type { BaseNode } from "./internal/buildNodeTree";
import { buildNodeTree } from "./internal/buildNodeTree";
import type { TreeInlineCreateState, TreeState } from "./types";

type TreeAction =
  | { type: "setNodes"; nodes: BaseNode[] }
  | { type: "select"; id: string | null }
  | { type: "toggleExpanded"; id: string }
  | { type: "setExpanded"; ids: string[] }
  | { type: "setInlineCreate"; inlineCreate: TreeInlineCreateState | null };

const ensureSelection = (state: TreeState): TreeState => {
  if (!state.selectedId) return state;
  const exists = state.flat.some((node) => node._id === state.selectedId);
  return exists ? state : { ...state, selectedId: null };
};

export const createInitialTreeState = (
  nodes: BaseNode[] = [],
  selectedId: string | null = null,
  expandedIds: string[] = [],
): TreeState => {
  const tree = buildNodeTree(nodes);
  const initialSelected = selectedId ?? null;
  const normalizedSelected = tree.flat.some(
    (node) => node._id === initialSelected,
  )
    ? initialSelected
    : null;

  return {
    nodes,
    tree: tree.roots,
    flat: tree.flat,
    expandedIds: [...expandedIds],
    selectedId: normalizedSelected,
    inlineCreate: null,
  };
};

export const treeReducer = (
  state: TreeState,
  action: TreeAction,
): TreeState => {
  switch (action.type) {
    case "setNodes": {
      const tree = buildNodeTree(action.nodes);
      return ensureSelection({
        ...state,
        nodes: action.nodes,
        tree: tree.roots,
        flat: tree.flat,
      });
    }

    case "select":
      return state.selectedId === action.id
        ? state
        : { ...state, selectedId: action.id };

    case "toggleExpanded": {
      const isExpanded = state.expandedIds.includes(action.id);
      return {
        ...state,
        expandedIds: isExpanded
          ? state.expandedIds.filter((v) => v !== action.id)
          : [...state.expandedIds, action.id],
      };
    }

    case "setExpanded":
      return { ...state, expandedIds: [...action.ids] };

    case "setInlineCreate":
      return { ...state, inlineCreate: action.inlineCreate ?? null };

    default:
      return state;
  }
};
