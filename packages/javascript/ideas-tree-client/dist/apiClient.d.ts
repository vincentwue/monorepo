import type { IdeaNodeView, ReorderDirection } from "./types.js";
export interface IdeasApiClientOptions {
    /**
     * Base URL of the core_server API, e.g. "http://localhost:8000".
     * Must NOT include a trailing slash.
     */
    baseUrl: string;
}
/**
 * Example usage in a web app:
 *
 * ```ts
 * const client = new IdeasApiClient({ baseUrl: import.meta.env.VITE_API_URL });
 * const children = await client.listChildren(parentId);
 * ```
 */
export declare class IdeasApiClient {
    private readonly http;
    constructor(options: IdeasApiClientOptions);
    listChildren(parentId: string | null): Promise<IdeaNodeView[]>;
    createChild(parentId: string | null, title: string, note?: string): Promise<IdeaNodeView>;
    moveNode(nodeId: string, newParentId: string | null): Promise<IdeaNodeView>;
    reorderNode(nodeId: string, direction: ReorderDirection, targetRank?: number): Promise<IdeaNodeView>;
}
//# sourceMappingURL=apiClient.d.ts.map