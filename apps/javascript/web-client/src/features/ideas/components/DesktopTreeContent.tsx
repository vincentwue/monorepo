import { useEffect, useRef } from "react";

import type { IdeaNodeView, ReorderDirection } from "@ideas/tree-client";
import { ThemedTreeView, useTreeActions, useTreeState } from "@monorepo/tree";

import { arraysEqual } from "../utils/treeNodes";
import { detectTreeMutation, type TreeMutation } from "./treeMutations";

export interface DesktopTreeContentProps {
  onReorderNode: (nodeId: string, direction: ReorderDirection) => Promise<void>;
  onMoveNode: (nodeId: string, newParentId: string | null) => Promise<void>;
  onCreateIdea: (parentId: string | null, title: string) => Promise<IdeaNodeView>;
  initialExpandedIds: string[];
  initialSelectedId: string | null;
  initialStateKey: string;
  onExpandedIdsChange: (ids: string[]) => void;
  onSelectionChange: (selectedId: string | null) => void;
  settingsHydrated: boolean;
}

export type TreeViewNode = ReturnType<typeof useTreeState>["flat"][number];
type InlineCreateState = ReturnType<typeof useTreeState>["inlineCreate"];
type TreeStateNode = ReturnType<typeof useTreeState>["nodes"][number];

export function DesktopTreeContent({
  onReorderNode,
  onMoveNode,
  onCreateIdea,
  initialExpandedIds,
  initialSelectedId,
  initialStateKey,
  onExpandedIdsChange,
  onSelectionChange,
  settingsHydrated,
}: DesktopTreeContentProps) {
  const { tree, expandedIds, selectedId, flat, inlineCreate, nodes: stateNodes } =
    useTreeState();
  const actions = useTreeActions();
  const appliedSettingsKeyRef = useRef<string | null>(null);
  const reportedExpandedRef = useRef<string[]>(expandedIds);
  const reportedSelectedRef = useRef<string | null>(selectedId ?? null);
  const pendingInlineCreateRef = useRef<InlineCreateState | null>(null);
  const previousNodesRef = useRef(stateNodes);
  const syncingTreeMutationRef = useRef(false);

  useEffect(() => {
    if (!settingsHydrated) return;
    if (!initialStateKey) return;
    if (appliedSettingsKeyRef.current === initialStateKey) return;
    actions.setExpanded(initialExpandedIds);
    actions.select(initialSelectedId ?? null);
    appliedSettingsKeyRef.current = initialStateKey;
  }, [actions, initialExpandedIds, initialSelectedId, initialStateKey, settingsHydrated]);

  useEffect(() => {
    if (!settingsHydrated) return;
    if (arraysEqual(expandedIds, reportedExpandedRef.current)) return;
    reportedExpandedRef.current = expandedIds;
    onExpandedIdsChange(expandedIds);
  }, [expandedIds, onExpandedIdsChange, settingsHydrated]);

  useEffect(() => {
    if (!settingsHydrated) return;
    const normalized = selectedId ?? null;
    if (reportedSelectedRef.current === normalized) return;
    reportedSelectedRef.current = normalized;
    onSelectionChange(normalized);
  }, [selectedId, onSelectionChange, settingsHydrated]);

  useEffect(() => {
    if (inlineCreate) {
      pendingInlineCreateRef.current = inlineCreate;
      return;
    }
    const pending = pendingInlineCreateRef.current;
    if (!pending) return;
    pendingInlineCreateRef.current = null;
    if (!pending.tempId) return;
    const placeholderNode = flat.find((node) => node._id === pending.tempId);
    if (!placeholderNode) {
      return;
    }
    const parentId = (placeholderNode.parent_id ?? null) as string | null;
    const title = placeholderNode.title?.trim() || "Untitled idea";

    void (async () => {
      try {
        const created = await onCreateIdea(parentId, title);
        const finalId = created.id ?? pending.tempId;
        actions.confirmInlineCreate({
          tempId: pending.tempId,
          nodeId: finalId,
        });
      } catch (err) {
        console.error("[DesktopIdeasTree] inline create failed", err);
        actions.delete(pending.tempId);
        actions.select(pending.previousSelectedId ?? null);
      }
    })();
  }, [inlineCreate, flat, onCreateIdea, actions]);

  useEffect(() => {
    if (!settingsHydrated) {
      previousNodesRef.current = stateNodes;
      return;
    }
    const prevNodes = previousNodesRef.current;
    previousNodesRef.current = stateNodes;
    if (!prevNodes?.length) return;
    if (syncingTreeMutationRef.current) return;

    const mutation: TreeMutation | null = detectTreeMutation(prevNodes, stateNodes);
    if (!mutation) return;

    syncingTreeMutationRef.current = true;
    let cancelled = false;
    const syncMutation = async () => {
      try {
        if (mutation.type === "move") {
          await onMoveNode(mutation.nodeId, mutation.newParentId);
        } else {
          await onReorderNode(mutation.nodeId, mutation.direction);
        }
      } catch (err) {
        console.error("[DesktopIdeasTree] failed to sync tree mutation", err);
      } finally {
        if (!cancelled) {
          syncingTreeMutationRef.current = false;
        }
      }
    };
    void syncMutation();
    return () => {
      cancelled = true;
      syncingTreeMutationRef.current = false;
    };
  }, [stateNodes, settingsHydrated, onMoveNode, onReorderNode]);

  const hasTree = tree.length > 0;

  return (
    <div className="flex flex-col gap-4">
      {hasTree ? (
        <div className="rounded-[32px] border border-slate-800/70 bg-slate-950/40 p-1 shadow-lg shadow-slate-900/40">
          <ThemedTreeView
            className="w-full rounded-[28px]"
            style={{
              minHeight: "auto",
              background: "radial-gradient(circle at top, rgba(56,189,248,0.14), rgba(2,6,23,0.92))",
              padding: "24px 28px",
            }}
          />
        </div>
      ) : (
        <p className="rounded-md border border-dashed border-slate-800/70 bg-slate-900/80 p-4 text-sm text-slate-400">
          No ideas available yet.
        </p>
      )}
    </div>
  );
}
