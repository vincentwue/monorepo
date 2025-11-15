import { useCallback, useEffect, useState } from "react";
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
export function useIdeasTree(parentId, client) {
    const [nodes, setNodes] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const refresh = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const data = await client.listChildren(parentId);
            setNodes(data);
        }
        catch (err) {
            console.error("Failed to load ideas children", err);
            setError(err?.message ?? "Failed to load ideas");
        }
        finally {
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
            }
            catch (err) {
                if (!cancelled) {
                    console.error("Failed to load ideas children", err);
                    setError(err?.message ?? "Failed to load ideas");
                }
            }
            finally {
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
    const createChild = useCallback(async (pId, title, note) => {
        try {
            await client.createChild(pId, title, note);
            await refresh();
        }
        catch (err) {
            console.error("Failed to create child idea", err);
            setError(err?.message ?? "Failed to create idea");
        }
    }, [client, refresh]);
    const moveNode = useCallback(async (nodeId, newParentId) => {
        try {
            await client.moveNode(nodeId, newParentId);
            await refresh();
        }
        catch (err) {
            console.error("Failed to move idea node", err);
            setError(err?.message ?? "Failed to move idea");
        }
    }, [client, refresh]);
    const reorderNode = useCallback(async (nodeId, direction) => {
        try {
            await client.reorderNode(nodeId, direction);
            await refresh();
        }
        catch (err) {
            console.error("Failed to reorder idea node", err);
            setError(err?.message ?? "Failed to reorder idea");
        }
    }, [client, refresh]);
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
