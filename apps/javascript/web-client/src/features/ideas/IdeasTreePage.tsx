import {
  IdeasApiClient,
  useIdeasTree,
  type IdeaNodeView,
  type ReorderDirection,
} from "@ideas/tree-client";
import {
  MobileTreeNavigator,
  type MobileTreeNavigatorProps,
  type MobileTreeNode,
} from "@monorepo/mobile-tree-ui";
import {
  ThemedTreeView,
  TreeKeyboardShortcuts,
  TreeProvider,
  useTreeActions,
  useTreeState,
} from "@monorepo/tree";
import { ArrowDown, ArrowUp, Plus } from "lucide-react";
import type { FormEvent } from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useMediaQuery } from "../../hooks/useMediaQuery";

interface ProviderNode {
  _id: string;
  parent_id: string | null;
  title: string;
  rank?: number;
}

const DESKTOP_TREE_KEY = "ideas-desktop-tree";
const DEFAULT_TREE_STATE: IdeaTreeUiState = {
  expandedIds: [],
  selectedId: null,
};

export function IdeasTreePage() {
  const isMobile = useMediaQuery("(max-width: 768px)");

  const apiBaseUrl = import.meta.env.VITE_API_URL ?? "";
  const client = useMemo(() => {
    if (!apiBaseUrl) {
      throw new Error("Missing VITE_API_URL environment variable.");
    }
    return new IdeasApiClient({ baseUrl: apiBaseUrl });
  }, [apiBaseUrl]);

  const { nodes, loading, error, reorderNode, createChild, moveNode } = useIdeasTree(null, client);

  const [ideaTreeSettings, setIdeaTreeSettings] = useState<IdeaTreeUiState>(DEFAULT_TREE_STATE);
  const [settingsHydrated, setSettingsHydrated] = useState(false);
  const [settingsError, setSettingsError] = useState<string | null>(null);
  const [settingsDirty, setSettingsDirty] = useState(false);
  const [settingsSaving, setSettingsSaving] = useState(false);

  const applyRemoteSettings = useCallback((next: IdeaTreeUiState) => {
    setIdeaTreeSettings(next);
    setSettingsDirty(false);
  }, []);

  useEffect(() => {
    let cancelled = false;

    const loadSettings = async () => {
      try {
        const state = await client.getIdeaTreeState();
        if (cancelled) return;
        applyRemoteSettings(state);
        setSettingsHydrated(true);
        setSettingsError(null);
      } catch (err: unknown) {
        if (cancelled) return;
        console.error("[IdeasTreePage] failed to load tree settings", err);
        setSettingsHydrated(true);
        setSettingsError(err instanceof Error ? err.message : "Failed to load tree view");
      }
    };

    loadSettings();

    return () => {
      cancelled = true;
    };
  }, [client, applyRemoteSettings]);

  const updateTreeSettings = useCallback(
    (updater: (prev: IdeaTreeUiState) => IdeaTreeUiState) => {
      let changed = false;
      setIdeaTreeSettings((prev) => {
        const next = updater(prev);
        if (
          next === prev ||
          (next.selectedId === prev.selectedId && arraysEqual(next.expandedIds, prev.expandedIds))
        ) {
          return prev;
        }
        changed = true;
        return next;
      });
      if (changed && settingsHydrated) {
        setSettingsDirty(true);
      }
    },
    [settingsHydrated],
  );

  useEffect(() => {
    if (!settingsHydrated || !settingsDirty) return;

    const timeout = window.setTimeout(() => {
      setSettingsSaving(true);
      client
        .updateIdeaTreeState(ideaTreeSettings)
        .then((next) => {
          applyRemoteSettings(next);
          setSettingsSaving(false);
          setSettingsError(null);
        })
        .catch((err: unknown) => {
          console.error("[IdeasTreePage] failed to save tree settings", err);
          setSettingsSaving(false);
          setSettingsError(
            err instanceof Error ? err.message : "Failed to save tree view settings",
          );
        });
    }, 600);

    return () => {
      window.clearTimeout(timeout);
    };
  }, [client, ideaTreeSettings, settingsDirty, settingsHydrated, applyRemoteSettings]);

  const settingsKey = useMemo(() => buildSettingsKey(ideaTreeSettings), [ideaTreeSettings]);

  const handleExpandedIdsChange = useCallback(
    (ids: string[]) => {
      const normalized = normalizeExpandedIds(ids);
      updateTreeSettings((prev) => ({ ...prev, expandedIds: normalized }));
    },
    [updateTreeSettings],
  );

  const handleSelectionChange = useCallback(
    (selectedId: string | null) => {
      updateTreeSettings((prev) => ({ ...prev, selectedId: selectedId ?? null }));
    },
    [updateTreeSettings],
  );

  const handleMobilePathChange = useCallback<NonNullable<MobileTreeNavigatorProps["onPathChange"]>>(
    (path) => {
      const expandedIds = normalizeExpandedIds(
        path
          .map((crumb) => crumb?.id ?? null)
          .filter((id): id is string => typeof id === "string" && id.length > 0),
      );
      const selectedId = path.length ? path[path.length - 1]?.id ?? null : null;
      updateTreeSettings((prev) => ({ ...prev, expandedIds, selectedId: selectedId ?? null }));
    },
    [updateTreeSettings],
  );

  const providerNodes = useMemo(() => mapToProviderNodes(nodes), [nodes]);
  const mobileNodes = useMemo(() => mapToMobileNodes(nodes), [nodes]);
  const nodesVersion = useMemo(() => buildNodesVersion(nodes), [nodes]);

  const normalizedError = error
    ? typeof error === "string"
      ? error
      : String(error)
    : null;

  const [creatingIdea, setCreatingIdea] = useState(false);
  const [ideaMutationError, setIdeaMutationError] = useState<string | null>(null);

  const handleCreateIdea = useCallback(
    async (parentId: string | null, rawTitle: string): Promise<IdeaNodeView> => {
      const title = rawTitle.trim() || "Untitled idea";
      setCreatingIdea(true);
      setIdeaMutationError(null);
      try {
        const created = await createChild(parentId, title);
        return created;
      } catch (err: unknown) {
        console.error("[IdeasTreePage] failed to create idea", err);
        const message = err instanceof Error ? err.message : "Failed to create idea";
        setIdeaMutationError(message);
        throw err;
      } finally {
        setCreatingIdea(false);
      }
    },
    [createChild],
  );

  const handleReorderNode = useCallback(
    async (nodeId: string, direction: ReorderDirection) => {
      setIdeaMutationError(null);
      try {
        await reorderNode(nodeId, direction);
      } catch (err: unknown) {
        console.error("[IdeasTreePage] failed to reorder idea", err);
        const message = err instanceof Error ? err.message : "Failed to reorder idea";
        setIdeaMutationError(message);
        throw err;
      }
    },
    [reorderNode],
  );

  const handleMoveNode = useCallback(
    async (nodeId: string, newParentId: string | null) => {
      setIdeaMutationError(null);
      try {
        await moveNode(nodeId, newParentId);
      } catch (err: unknown) {
        console.error("[IdeasTreePage] failed to move idea", err);
        const message = err instanceof Error ? err.message : "Failed to move idea";
        setIdeaMutationError(message);
        throw err;
      }
    },
    [moveNode],
  );

  const handleCreateRootPrompt = useCallback(async () => {
    const title = window.prompt("Name your new idea", "New idea");
    if (title === null) return;
    try {
      await handleCreateIdea(null, title);
    } catch {
      // error already logged & stored
    }
  }, [handleCreateIdea]);

  return isMobile ? (
    <MobileIdeasTree
      componentKey={nodesVersion}
      nodes={mobileNodes}
      loading={loading}
      error={normalizedError}
      initialSelectedId={ideaTreeSettings.selectedId}
      onPathChange={handleMobilePathChange}
      settingsSaving={settingsSaving}
      settingsError={settingsError}
      onCreateRoot={handleCreateRootPrompt}
      creatingIdea={creatingIdea}
      mutationError={ideaMutationError}
      onCreateIdea={handleCreateIdea}
    />
  ) : (
    <DesktopIdeasTree
      componentKey={nodesVersion}
      nodes={providerNodes}
      loading={loading}
      error={normalizedError}
      onReorderNode={handleReorderNode}
      onMoveNode={handleMoveNode}
      initialExpandedIds={ideaTreeSettings.expandedIds}
      initialSelectedId={ideaTreeSettings.selectedId}
      initialStateKey={settingsKey}
      onExpandedChange={handleExpandedIdsChange}
      onSelectionChange={handleSelectionChange}
      settingsHydrated={settingsHydrated}
      settingsSaving={settingsSaving}
      settingsError={settingsError}
      onCreateRoot={handleCreateRootPrompt}
      onCreateIdea={handleCreateIdea}
      creatingIdea={creatingIdea}
      mutationError={ideaMutationError}
    />
  );
}

interface DesktopIdeasTreeProps {
  nodes: ProviderNode[];
  componentKey: string;
  loading: boolean;
  error: string | null;
  onReorderNode: (nodeId: string, direction: ReorderDirection) => Promise<void>;
  onMoveNode: (nodeId: string, newParentId: string | null) => Promise<void>;
  initialExpandedIds: string[];
  initialSelectedId: string | null;
  initialStateKey: string;
  onExpandedChange: (ids: string[]) => void;
  onSelectionChange: (selectedId: string | null) => void;
  settingsHydrated: boolean;
  settingsSaving: boolean;
  settingsError: string | null;
  onCreateRoot: () => Promise<void> | void;
  onCreateIdea: (parentId: string | null, title: string) => Promise<IdeaNodeView>;
  creatingIdea: boolean;
  mutationError: string | null;
}

function DesktopIdeasTree({
  nodes,
  componentKey,
  loading,
  error,
  onReorderNode,
  onMoveNode,
  initialExpandedIds,
  initialSelectedId,
  initialStateKey,
  onExpandedChange,
  onSelectionChange,
  settingsHydrated,
  settingsSaving,
  settingsError,
  onCreateRoot,
  onCreateIdea,
  creatingIdea,
  mutationError,
}: DesktopIdeasTreeProps) {
  return (
    <div className="flex flex-1 flex-col gap-2 p-3">
      <header className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-200">Ideas (Desktop)</h2>
        <div className="flex items-center gap-3 text-xs">
          {settingsSaving ? (
            <span className="text-slate-400">Saving view...</span>
          ) : settingsError ? (
            <span className="text-red-400">{settingsError}</span>
          ) : null}
          <button
            type="button"
            className="rounded border border-slate-700 px-2 py-1 text-xs text-slate-100 hover:bg-slate-800 disabled:opacity-50"
            onClick={() => {
              void onCreateRoot();
            }}
            disabled={creatingIdea}
          >
            {creatingIdea ? "Creating..." : "New idea"}
          </button>
        </div>
      </header>
      {loading && <p className="text-xs text-slate-400">Loading tree...</p>}
      {error && <p className="text-xs text-red-400">{error}</p>}
      <div className="flex-1 min-h-0 overflow-y-auto">
        <TreeProvider
          key={`${DESKTOP_TREE_KEY}-${componentKey}`}
          treeKey={DESKTOP_TREE_KEY}
          nodes={nodes}
        >
          <TreeKeyboardShortcuts treeKey={DESKTOP_TREE_KEY}>
            <DesktopTreeContent
              disableActions={loading}
              onReorderNode={onReorderNode}
              onMoveNode={onMoveNode}
              onCreateIdea={onCreateIdea}
              initialExpandedIds={initialExpandedIds}
              initialSelectedId={initialSelectedId}
              initialStateKey={initialStateKey}
              onExpandedIdsChange={onExpandedChange}
              onSelectionChange={onSelectionChange}
              settingsHydrated={settingsHydrated}
              creatingIdea={creatingIdea}
              mutationError={mutationError}
            />
          </TreeKeyboardShortcuts>
        </TreeProvider>
      </div>
    </div>
  );
}

interface DesktopTreeContentProps {
  disableActions: boolean;
  onReorderNode: (nodeId: string, direction: ReorderDirection) => Promise<void>;
  onMoveNode: (nodeId: string, newParentId: string | null) => Promise<void>;
  onCreateIdea: (parentId: string | null, title: string) => Promise<IdeaNodeView>;
  initialExpandedIds: string[];
  initialSelectedId: string | null;
  initialStateKey: string;
  onExpandedIdsChange: (ids: string[]) => void;
  onSelectionChange: (selectedId: string | null) => void;
  settingsHydrated: boolean;
  creatingIdea: boolean;
  mutationError: string | null;
}

type TreeViewNode = ReturnType<typeof useTreeState>["flat"][number];
type InlineCreateState = ReturnType<typeof useTreeState>["inlineCreate"];
type TreeStateNode = ReturnType<typeof useTreeState>["nodes"][number];

function DesktopTreeContent({
  disableActions,
  onReorderNode,
  onMoveNode,
  onCreateIdea,
  initialExpandedIds,
  initialSelectedId,
  initialStateKey,
  onExpandedIdsChange,
  onSelectionChange,
  settingsHydrated,
  creatingIdea,
  mutationError,
}: DesktopTreeContentProps) {
  const { tree, expandedIds, selectedId, flat, inlineCreate, nodes: stateNodes } = useTreeState();
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
        console.error("[IdeasTreePage] inline create failed", err);
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

    const mutation = detectTreeMutation(prevNodes, stateNodes);
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
        console.error("[IdeasTreePage] failed to sync tree mutation", err);
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

  const selectedNode = useMemo(
    () => (selectedId ? flat.find((node) => node._id === selectedId) ?? null : null),
    [flat, selectedId],
  );
  const hasTree = tree.length > 0;

  return (
    <div className="flex flex-col gap-4">
      {hasTree ? (
        <div className="rounded-[32px] border border-slate-800/70 bg-slate-950/40 p-1 shadow-lg shadow-slate-900/40">
          <ThemedTreeView
            className="w-full rounded-[28px]"
            style={{
              minHeight: "auto",
              background:
                "radial-gradient(circle at top, rgba(56,189,248,0.14), rgba(2,6,23,0.92))",
              padding: "24px 28px",
            }}
          />
        </div>
      ) : (
        <p className="rounded-md border border-dashed border-slate-800/70 bg-slate-900/80 p-4 text-sm text-slate-400">
          No ideas available yet.
        </p>
      )}
      <DesktopTreeActionPanel
        selectedNode={selectedNode}
        disableActions={disableActions || !hasTree}
        creatingIdea={creatingIdea}
        onCreateIdea={onCreateIdea}
        onReorderNode={onReorderNode}
        mutationError={mutationError}
      />
    </div>
  );
}

interface DesktopTreeActionPanelProps {
  selectedNode: TreeViewNode | null;
  disableActions: boolean;
  creatingIdea: boolean;
  onCreateIdea: (parentId: string | null, title: string) => Promise<IdeaNodeView>;
  onReorderNode: (nodeId: string, direction: ReorderDirection) => Promise<void>;
  mutationError: string | null;
}

function DesktopTreeActionPanel({
  selectedNode,
  disableActions,
  creatingIdea,
  onCreateIdea,
  onReorderNode,
  mutationError,
}: DesktopTreeActionPanelProps) {
  const [childTitle, setChildTitle] = useState("");
  const [pendingAction, setPendingAction] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const selectedNodeId = selectedNode?._id ?? null;

  useEffect(() => {
    setLocalError(null);
  }, [selectedNodeId]);

  const handleCreateChild = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      if (disableActions || !selectedNodeId) {
        setLocalError("Select an idea to add a child.");
        return;
      }
      const title = childTitle.trim();
      if (!title) {
        setLocalError("Enter a title for the new idea.");
        return;
      }
      setPendingAction(true);
      setLocalError(null);
      try {
        await onCreateIdea(selectedNodeId, title);
        setChildTitle("");
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : "Failed to create idea";
        setLocalError(message);
      } finally {
        setPendingAction(false);
      }
    },
    [childTitle, disableActions, onCreateIdea, selectedNodeId],
  );

  const handleReorder = useCallback(
    async (direction: ReorderDirection) => {
      if (disableActions || !selectedNodeId) return;
      setPendingAction(true);
      setLocalError(null);
      try {
        await onReorderNode(selectedNodeId, direction);
      } catch (err: unknown) {
        const message =
          err instanceof Error ? err.message : "Failed to update idea order";
        setLocalError(message);
      } finally {
        setPendingAction(false);
      }
    },
    [disableActions, onReorderNode, selectedNodeId],
  );

  const inputDisabled = disableActions || pendingAction || !selectedNodeId;
  const disableCreate = inputDisabled || creatingIdea;
  const disableReorder = disableActions || pendingAction || !selectedNodeId;
  const activeTitle = selectedNode?.title?.trim() || "Select an idea from the tree";

  return (
    <div className="rounded-2xl border border-slate-800/70 bg-slate-950/60 p-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500">Selected idea</p>
          <p className="text-base font-semibold text-slate-100">{activeTitle}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            className="flex items-center gap-1 rounded-full border border-slate-700/80 px-3 py-1.5 text-xs font-semibold uppercase tracking-wide text-slate-200 transition hover:border-sky-400 hover:text-white disabled:opacity-40"
            onClick={() => {
              void handleReorder("up");
            }}
            disabled={disableReorder}
          >
            <ArrowUp className="h-3.5 w-3.5" />
            Move up
          </button>
          <button
            type="button"
            className="flex items-center gap-1 rounded-full border border-slate-700/80 px-3 py-1.5 text-xs font-semibold uppercase tracking-wide text-slate-200 transition hover:border-sky-400 hover:text-white disabled:opacity-40"
            onClick={() => {
              void handleReorder("down");
            }}
            disabled={disableReorder}
          >
            <ArrowDown className="h-3.5 w-3.5" />
            Move down
          </button>
        </div>
      </div>
      <form
        onSubmit={handleCreateChild}
        className="mt-4 flex flex-col gap-2 sm:flex-row sm:items-center"
      >
        <div className="flex-1">
          <label className="text-xs font-medium uppercase tracking-wide text-slate-500">
            Add child idea
          </label>
          <input
            type="text"
            className="mt-1 w-full rounded-xl border border-slate-700/70 bg-slate-900/60 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:border-sky-500 focus:outline-none"
            placeholder={
              selectedNodeId ? "Name your new idea" : "Select an idea to add a child"
            }
            value={childTitle}
            onChange={(event) => {
              setChildTitle(event.target.value);
              setLocalError(null);
            }}
            disabled={inputDisabled}
          />
        </div>
        <button
          type="submit"
          className="flex items-center justify-center gap-1 rounded-xl bg-sky-600 px-4 py-2 text-sm font-semibold text-white shadow shadow-sky-900/60 transition hover:bg-sky-500 disabled:cursor-not-allowed disabled:opacity-50"
          disabled={disableCreate}
        >
          <Plus className="h-4 w-4" />
          Add child
        </button>
      </form>
      {(localError || mutationError) && (
        <p className="mt-2 text-xs text-rose-300">{localError ?? mutationError}</p>
      )}
    </div>
  );
}

interface MobileIdeasTreeProps {
  componentKey: string;
  nodes: MobileTreeNode[];
  loading: boolean;
  error: string | null;
  initialSelectedId: string | null;
  onPathChange?: MobileTreeNavigatorProps["onPathChange"];
  settingsSaving: boolean;
  settingsError: string | null;
  onCreateRoot: () => Promise<void> | void;
  creatingIdea: boolean;
  mutationError: string | null;
  onCreateIdea: (parentId: string | null, title: string) => Promise<IdeaNodeView>;
}

function MobileIdeasTree({
  componentKey,
  nodes,
  loading,
  error,
  initialSelectedId,
  onPathChange,
  settingsSaving,
  settingsError,
  onCreateRoot,
  creatingIdea,
  mutationError,
  onCreateIdea,
}: MobileIdeasTreeProps) {
  return (
    <div className="flex flex-1 flex-col gap-2 p-3">
      <header className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-200">Ideas (Mobile)</h2>
        <div className="flex items-center gap-2 text-xs">
          {settingsSaving ? (
            <span className="text-slate-400">Saving view...</span>
          ) : settingsError ? (
            <span className="text-red-400">{settingsError}</span>
          ) : null}
          <button
            type="button"
            className="rounded-full border border-slate-600 px-2 py-1 text-xs text-slate-100 disabled:opacity-50"
            onClick={() => {
              void onCreateRoot();
            }}
            disabled={creatingIdea}
          >
            {creatingIdea ? "Creating..." : "New idea"}
          </button>
        </div>
      </header>
      {mutationError && <p className="text-xs text-red-400">{mutationError}</p>}
      {loading && <p className="text-xs text-slate-400">Loading tree...</p>}
      {error && <p className="text-xs text-red-400">{error}</p>}
      <div className="flex-1 min-h-0 overflow-y-auto">
        {loading ? (
          <p className="p-3 text-sm text-slate-400">Preparing mobile tree...</p>
        ) : (
          <MobileTreeNavigator
            key={`mobile-${componentKey}`}
            nodes={nodes}
            className="shadow-none"
            initialNodeId={initialSelectedId ?? null}
            onPathChange={onPathChange}
            onCreateChild={async (parentId, title) => {
              await onCreateIdea(parentId, title);
            }}
            disabled={creatingIdea}
            errorMessage={mutationError}
          />
        )}
      </div>
    </div>
  );
}

const mapToProviderNodes = (list: IdeaNodeView[]): ProviderNode[] =>
  list.map((node) => ({
    _id: node.id,
    parent_id: node.parentId ?? null,
    title: node.title,
    rank: node.rank,
  }));

const mapToMobileNodes = (list: IdeaNodeView[]): MobileTreeNode[] =>
  list.map((node) => ({
    id: node.id,
    parentId: node.parentId ?? null,
    title: node.title,
    rank: node.rank ?? 0,
  }));

const buildNodesVersion = (list: IdeaNodeView[]): string =>
  list.length === 0
    ? "empty"
    : list
      .map((node) =>
        `${node.id}:${node.parentId ?? "root"}:${node.rank ?? 0}:${node.title ?? ""}`,
      )
      .join("|");

const buildSettingsKey = (state: IdeaTreeUiState): string =>
  `${state.selectedId ?? "root"}|${state.expandedIds.join(",")}`;

const arraysEqual = (a: readonly string[], b: readonly string[]): boolean =>
  a.length === b.length && a.every((value, index) => value === b[index]);

const normalizeExpandedIds = (ids: string[]): string[] => {
  const seen = new Set<string>();
  const normalized: string[] = [];
  for (const raw of ids) {
    if (typeof raw !== "string") continue;
    const value = raw.trim();
    if (!value || seen.has(value)) continue;
    seen.add(value);
    normalized.push(value);
  }
  return normalized;
};

type TreeMutation =
  | { type: "move"; nodeId: string; newParentId: string | null }
  | { type: "reorder"; nodeId: string; direction: ReorderDirection };

interface NodeOrderInfo {
  parentId: string | null;
  order: number;
}

const normalizeParentId = (value: string | null | undefined): string | null => value ?? null;

const isPlaceholderNode = (node?: TreeStateNode): boolean =>
  Boolean(node && (node as any).isPlaceholder);

const readUpdatedAt = (node: TreeStateNode): string | null => {
  const value = (node as any).updated_at;
  return typeof value === "string" ? value : null;
};

const buildNodeOrderMap = (nodes: TreeStateNode[]): Map<string, NodeOrderInfo> => {
  const buckets = new Map<string | null, TreeStateNode[]>();

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
        return a._id.localeCompare(b._id);
      })
      .forEach((node, index) => {
        orderMap.set(node._id, { parentId, order: index });
      });
  }

  return orderMap;
};

function detectTreeMutation(prevNodes: TreeStateNode[], nextNodes: TreeStateNode[]): TreeMutation | null {
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
