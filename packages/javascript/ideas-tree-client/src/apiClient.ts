import axios, { type AxiosInstance } from "axios";
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
export class IdeasApiClient {
  private readonly http: AxiosInstance;

  constructor(options: IdeasApiClientOptions) {
    const baseUrl = options.baseUrl.replace(/\/$/, "");

    this.http = axios.create({
      baseURL: baseUrl,
      withCredentials: true,
    });
  }

  async listChildren(parentId: string | null): Promise<IdeaNodeView[]> {
    const params: Record<string, string> = {};
    if (parentId != null) {
      params.parent_id = parentId;
    }

    const res = await this.http.get<IdeaNodeView[]>("/ideas/children", { params });
    return res.data;
  }

  async createChild(
    parentId: string | null,
    title: string,
    note?: string,
  ): Promise<IdeaNodeView> {
    const params: Record<string, string> = {};
    if (parentId != null) {
      params.parent_id = parentId;
    }

    const body: { title: string; note?: string } = { title };
    if (note !== undefined) {
      body.note = note;
    }

    const res = await this.http.post<IdeaNodeView>("/ideas/children", body, { params });
    return res.data;
  }

  async moveNode(
    nodeId: string,
    newParentId: string | null,
  ): Promise<IdeaNodeView> {
    const body: { new_parent_id: string | null } = {
      new_parent_id: newParentId,
    };

    const res = await this.http.post<IdeaNodeView>(
      `/ideas/nodes/${encodeURIComponent(nodeId)}/move`,
      body,
    );
    return res.data;
  }

  async reorderNode(
    nodeId: string,
    direction: ReorderDirection,
    targetRank?: number,
  ): Promise<IdeaNodeView> {
    const body: { direction: ReorderDirection; target_rank?: number } = {
      direction,
    };

    if (typeof targetRank === "number") {
      body.target_rank = targetRank;
    }

    const res = await this.http.post<IdeaNodeView>(
      `/ideas/nodes/${encodeURIComponent(nodeId)}/reorder`,
      body,
    );
    return res.data;
  }
}
