import { useCallback, useEffect, useState } from "react";

import type { IdeasApiClient } from "./apiClient.js";
import type { IdeaNodeView, ReorderDirection } from "./types.js";

export interface UseIdeasTreeResult {
  nodes: IdeaNodeView[];
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  createChild: (parentId: string | null, title: string, note?: string) => Promise<void>;
  moveNode: (nodeId: string, newParentId: string | null) => Promise<void>;
  reorderNode: (nodeId: string, direction: ReorderDirection) => Promise<void>;
}

/**
 * React hook that wraps IdeasApiClient and manages state for children under a parent.
 *
 * Example usage:
 *
 * ```ts
 * const client = new IdeasApiClient({ baseUrl: import.meta.env.VITE_API_URL });
 * const { nodes, createChild } = useIdeasTree(activeParentId, client);
 * ```
 */
export function useIdeasTree(parentId: string | null, client: IdeasApiClient): UseIdeasTreeResult {
  const [nodes, setNodes] = useState<IdeaNodeView[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await client.listChildren(parentId);
      setNodes(data);
    } catch (err: any) {
      console.error("Failed to load ideas children", err);
      setError(err?.message ?? "Failed to load ideas");
    } finally {
      setLoading(false);
    }
  }, [client, parentId]);

  useEffect(() => {
    let cancelled = false;

    const run = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await client.listChildren(parentId);
        if (!cancelled) {
          setNodes(data);
        }
      } catch (err: any) {
        if (!cancelled) {
          console.error("Failed to load ideas children", err);
          setError(err?.message ?? "Failed to load ideas");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    run();

    return () => {
      cancelled = true;
    };
  }, [client, parentId]);

  const createChild = useCallback(
    async (pId: string | null, title: string, note?: string) => {
      try {
        await client.createChild(pId, title, note);
        await refresh();
      } catch (err: any) {
        console.error("Failed to create child idea", err);
        setError(err?.message ?? "Failed to create idea");
      }
    },
    [client, refresh],
  );

  const moveNode = useCallback(
    async (nodeId: string, newParentId: string | null) => {
      try {
        await client.moveNode(nodeId, newParentId);
        await refresh();
      } catch (err: any) {
        console.error("Failed to move idea node", err);
        setError(err?.message ?? "Failed to move idea");
      }
    },
    [client, refresh],
  );

  const reorderNode = useCallback(
    async (nodeId: string, direction: ReorderDirection) => {
      try {
        await client.reorderNode(nodeId, direction);
        await refresh();
      } catch (err: any) {
        console.error("Failed to reorder idea node", err);
        setError(err?.message ?? "Failed to reorder idea");
      }
    },
    [client, refresh],
  );

  return {
    nodes,
    loading,
    error,
    refresh,
    createChild,
    moveNode,
    reorderNode,
  };
}
