import {
  IdeasApiClient,
  useIdeasTree,
  type IdeaNodeView,
  type ReorderDirection,
} from "@ideas/tree-client";
import { useCallback, useMemo, useState } from "react";

import { useMediaQuery } from "../../hooks/useMediaQuery";
import { DesktopIdeasTree } from "./components/DesktopIdeasTree";
import { MobileIdeasTree } from "./components/MobileIdeasTree";
import { useIdeaTreeSettings } from "./hooks/useIdeaTreeSettings";
import {
  buildNodesVersion,
  mapToMobileNodes,
  mapToProviderNodes,
} from "./utils/treeNodes";

export function IdeasTreePage() {
  const isMobile = useMediaQuery("(max-width: 768px)");

  const apiBaseUrl = import.meta.env.VITE_API_URL ?? "";
  const client = useMemo(() => {
    if (!apiBaseUrl) {
      throw new Error("Missing VITE_API_URL environment variable.");
    }
    return new IdeasApiClient({ baseUrl: apiBaseUrl });
  }, [apiBaseUrl]);

  const { nodes, loading, error, reorderNode, createChild, moveNode, deleteNode } = useIdeasTree(
    null,
    client,
  );

  const {
    ideaTreeSettings,
    settingsHydrated,
    settingsSaving,
    settingsError,
    settingsKey,
    handleExpandedIdsChange,
    handleSelectionChange,
    handleMobilePathChange,
  } = useIdeaTreeSettings(client);

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

  const handleDeleteNode = useCallback(
    async (nodeId: string) => {
      setIdeaMutationError(null);
      try {
        await deleteNode(nodeId);
      } catch (err: unknown) {
        console.error("[IdeasTreePage] failed to delete idea", err);
        const message = err instanceof Error ? err.message : "Failed to delete idea";
        setIdeaMutationError(message);
        throw err;
      }
    },
    [deleteNode],
  );

  const handleCreateRootPrompt = useCallback(async () => {
    const title = window.prompt("Name your new idea", "New idea");
    if (title === null) return;
    try {
      await handleCreateIdea(null, title);
    } catch {
      // Error already surfaced via mutation error state.
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
      onDeleteNode={handleDeleteNode}
      initialExpandedIds={ideaTreeSettings.expandedIds}
      initialSelectedId={ideaTreeSettings.selectedId}
      initialStateKey={settingsKey}
      onExpandedChange={handleExpandedIdsChange}
      onSelectionChange={handleSelectionChange}
      settingsHydrated={settingsHydrated}
      onCreateIdea={handleCreateIdea}
    />
  );
}
