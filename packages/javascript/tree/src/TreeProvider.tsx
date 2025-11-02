// src/TreeProvider.tsx
import React, { useEffect, useMemo, useReducer } from "react";
import { TreeActionsContext, TreeStateContext } from "./context";
import {
  addInlineCreatePlaceholder,
  beginInlineCreate,
  cancelInlineCreate,
  confirmInlineCreate,
  deleteNode,
  indentNode,
  moveNode,
  outdentNode,
  updateNodeTitle
} from "./mutations";
import { registerTree, unregisterTree } from "./registry";
import { createInitialTreeState, treeReducer } from "./treeReducer";
import type { TreeActions, TreePersistence, TreeState } from "./types";

interface TreeProviderProps {
  treeKey: string;
  nodes: any[];
  children: React.ReactNode;
  persistence?: TreePersistence;
}

export const TreeProvider = ({
  treeKey,
  nodes,
  children,
  persistence,
}: TreeProviderProps) => {
  const [state, dispatch] = useReducer(treeReducer, createInitialTreeState(nodes));

  // --- Core action set ---
  const baseActions = useMemo<TreeActions>(() => ({
    setNodes: (nodes) => dispatch({ type: "setNodes", nodes }),
    select: (id) => dispatch({ type: "select", id }),
    toggleExpanded: (id) => dispatch({ type: "toggleExpanded", id }),
    setExpanded: (ids) => dispatch({ type: "setExpanded", ids }),
    setInlineCreate: (inlineCreate) =>
      dispatch({ type: "setInlineCreate", inlineCreate }),
  }), []);

  // --- Mutation helpers ---
  const applyMutation = (mutator: (state: TreeState) => TreeState | null) => {
    const next = mutator(state);
    if (next) {
      dispatch({ type: "setNodes", nodes: next.nodes });
      dispatch({ type: "setExpanded", ids: next.expandedIds });
      dispatch({ type: "select", id: next.selectedId });
      dispatch({ type: "setInlineCreate", inlineCreate: next.inlineCreate });
    }
  };

  const extra = useMemo(() => ({
    indent: (id: string) => applyMutation((s) => indentNode(s, id)),
    outdent: (id: string) => applyMutation((s) => outdentNode(s, id)),
    moveUp: (id: string) => applyMutation((s) => moveNode(s, id, -1)),
    moveDown: (id: string) => applyMutation((s) => moveNode(s, id, 1)),
    rename: (id: string, title: string) =>
      applyMutation((s) => updateNodeTitle(s, { id, title })),
    delete: (id: string) => applyMutation((s) => deleteNode(s, id)),
    beginInlineCreate: (params: any) =>
      applyMutation((s) => beginInlineCreate(s, params)),
    addInlineCreatePlaceholder: (payload: any) =>
      applyMutation((s) => addInlineCreatePlaceholder(s, payload)),
    cancelInlineCreate: (tempId: string) =>
      applyMutation((s) => cancelInlineCreate(s, tempId)),
    confirmInlineCreate: (params: any) =>
      applyMutation((s) => confirmInlineCreate(s, params)),
  }), [state]);

  const allActions = { ...baseActions, ...extra };

  // --- Register once (no state dependency!) ---
  useEffect(() => {
    registerTree(treeKey, { getState: () => state, actions: allActions });
    return () => unregisterTree(treeKey);
  }, [treeKey]); // only depends on treeKey

  // --- Persistence side effects ---
  useEffect(() => {
    persistence?.onSelectionChange?.(state.selectedId);
  }, [state.selectedId]);
  useEffect(() => {
    persistence?.onExpandedChange?.(state.expandedIds);
  }, [state.expandedIds]);

  return (
    <TreeStateContext.Provider value={state}>
      <TreeActionsContext.Provider value={allActions}>
        {children}
      </TreeActionsContext.Provider>
    </TreeStateContext.Provider>
  );
};
