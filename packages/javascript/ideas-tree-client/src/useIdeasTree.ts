import { isAxiosError } from "axios";
import { useCallback, useEffect, useState } from "react";

import type { IdeasApiClient } from "./apiClient.js";
import type { IdeaNodeView, ReorderDirection } from "./types.js";

export interface UseIdeasTreeResult {
  nodes: IdeaNodeView[];
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  createChild: (
    parentId: string | null,
    title: string,
    note?: string
  ) => Promise<IdeaNodeView>;
  moveNode: (nodeId: string, newParentId: string | null) => Promise<void>;
  reorderNode: (nodeId: string, direction: ReorderDirection) => Promise<void>;
  deleteNode: (nodeId: string) => Promise<void>;
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
export function useIdeasTree(
  parentId: string | null,
  client: IdeasApiClient
): UseIdeasTreeResult {
  const [nodes, setNodes] = useState<IdeaNodeView[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchNodes = useCallback(async () => {
    if (parentId === null) {
      try {
        return await client.listTree();
      } catch (err: unknown) {
        if (isAxiosError(err) && err.response?.status === 404) {
          return client.listChildren(null);
        }
        throw err;
      }
    }
    return client.listChildren(parentId);
  }, [client, parentId]);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchNodes();
      setNodes(data);
    } catch (err: any) {
      console.error("Failed to load ideas children", err);
      setError(err?.message ?? "Failed to load ideas");
    } finally {
      setLoading(false);
    }
  }, [fetchNodes]);

  useEffect(() => {
    let cancelled = false;

    const run = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await fetchNodes();
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
  }, [fetchNodes]);

  const createChild = useCallback(
    async (pId: string | null, title: string, note?: string) => {
      try {
        const created = await client.createChild(pId, title, note);
        await refresh();
        return created;
      } catch (err: any) {
        console.error("Failed to create child idea", err);
        setError(err?.message ?? "Failed to create idea");
        throw err;
      }
    },
    [client, refresh]
  );

  const moveNode = useCallback(
    async (nodeId: string, newParentId: string | null) => {
      try {
        await client.moveNode(nodeId, newParentId);
        await refresh();
      } catch (err: any) {
        console.error("Failed to move idea node", err);
        setError(err?.message ?? "Failed to move idea");
        throw err;
      }
    },
    [client, refresh]
  );

  const reorderNode = useCallback(
    async (nodeId: string, direction: ReorderDirection) => {
      try {
        await client.reorderNode(nodeId, direction);
        await refresh();
      } catch (err: any) {
        console.error("Failed to reorder idea node", err);
        setError(err?.message ?? "Failed to reorder idea");
        throw err;
      }
    },
    [client, refresh]
  );

  const deleteNode = useCallback(
    async (nodeId: string) => {
      try {
        await client.deleteNode(nodeId);
        await refresh();
      } catch (err: any) {
        console.error("Failed to delete idea node", err);
        setError(err?.message ?? "Failed to delete idea");
        throw err;
      }
    },
    [client, refresh]
  );

  return {
    nodes,
    loading,
    error,
    refresh,
    createChild,
    moveNode,
    reorderNode,
    deleteNode,
  };
}
