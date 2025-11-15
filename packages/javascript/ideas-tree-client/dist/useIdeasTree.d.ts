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
export declare function useIdeasTree(parentId: string | null, client: IdeasApiClient): UseIdeasTreeResult;
//# sourceMappingURL=useIdeasTree.d.ts.map