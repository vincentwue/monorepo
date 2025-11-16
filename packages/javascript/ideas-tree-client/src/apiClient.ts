import axios, { type AxiosInstance } from "axios";
import type {
  IdeaNodeView,
  IdeaTreeUiState,
  ReorderDirection,
} from "./types.js";

export interface IdeasApiClientOptions {
  /**
   * Base URL of the core_server API, e.g. "https://api.example.com".
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
type IdeaNodeApiResponse = {
  id: string;
  parent_id?: string | null;
  parentId?: string | null;
  title: string;
  note?: string;
  rank?: number;
};

type IdeaTreeStateResponse = {
  expanded_ids?: unknown;
  selected_id?: string | null;
};

const normalizeIdeaNode = (node: IdeaNodeApiResponse): IdeaNodeView => ({
  id: node.id,
  parentId: node.parentId ?? node.parent_id ?? null,
  title: node.title,
  note: node.note,
  rank: typeof node.rank === "number" ? node.rank : 0,
});

const normalizeIdeaTreeState = (
  payload: IdeaTreeStateResponse
): IdeaTreeUiState => {
  const expandedIds = Array.isArray(payload.expanded_ids)
    ? payload.expanded_ids.filter(
        (value): value is string => typeof value === "string"
      )
    : [];

  return {
    expandedIds,
    selectedId: payload.selected_id ?? null,
  };
};

const serializeIdeaTreeState = (
  state: IdeaTreeUiState
): IdeaTreeStateResponse => {
  const expandedIds = state.expandedIds.filter(
    (value, index, array) =>
      typeof value === "string" &&
      value.length > 0 &&
      array.indexOf(value) === index
  );

  return {
    expanded_ids: expandedIds,
    selected_id: state.selectedId ?? null,
  };
};

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

    const res = await this.http.get<IdeaNodeApiResponse[]>("/ideas/children", {
      params,
    });
    return res.data.map(normalizeIdeaNode);
  }

  async listTree(): Promise<IdeaNodeView[]> {
    const res = await this.http.get<IdeaNodeApiResponse[]>("/ideas/tree");
    return res.data.map(normalizeIdeaNode);
  }

  async createChild(
    parentId: string | null,
    title: string,
    note?: string,
    afterId?: string | null
  ): Promise<IdeaNodeView> {
    const params: Record<string, string> = {};
    if (parentId != null) {
      params.parent_id = parentId;
    }
    if (typeof afterId === "string" && afterId.length > 0) {
      params.after_id = afterId;
    }

    const body: { title: string; note?: string } = { title };
    if (note !== undefined) {
      body.note = note;
    }

    const res = await this.http.post<IdeaNodeApiResponse>(
      "/ideas/children",
      body,
      { params }
    );
    return normalizeIdeaNode(res.data);
  }

  async moveNode(
    nodeId: string,
    newParentId: string | null
  ): Promise<IdeaNodeView> {
    const body: { new_parent_id: string | null } = {
      new_parent_id: newParentId,
    };

    const res = await this.http.post<IdeaNodeApiResponse>(
      `/ideas/nodes/${encodeURIComponent(nodeId)}/move`,
      body
    );
    return normalizeIdeaNode(res.data);
  }

  async reorderNode(
    nodeId: string,
    direction: ReorderDirection,
    targetIndex?: number
  ): Promise<IdeaNodeView> {
    const body: { direction: ReorderDirection; target_index?: number } = {
      direction,
    };

    if (typeof targetIndex === "number" && Number.isFinite(targetIndex)) {
      body.target_index = targetIndex;
    }

    const res = await this.http.post<IdeaNodeApiResponse>(
      `/ideas/nodes/${encodeURIComponent(nodeId)}/reorder`,
      body
    );
    return normalizeIdeaNode(res.data);
  }

  async renameNode(nodeId: string, title: string): Promise<IdeaNodeView> {
    const body = { title };
    const res = await this.http.patch<IdeaNodeApiResponse>(
      `/ideas/nodes/${encodeURIComponent(nodeId)}`,
      body
    );
    return normalizeIdeaNode(res.data);
  }

  async deleteNode(nodeId: string): Promise<void> {
    await this.http.delete(`/ideas/nodes/${encodeURIComponent(nodeId)}`);
  }

  async getIdeaTreeState(): Promise<IdeaTreeUiState> {
    const res = await this.http.get<IdeaTreeStateResponse>(
      "/settings/idea-tree"
    );
    return normalizeIdeaTreeState(res.data);
  }

  async updateIdeaTreeState(state: IdeaTreeUiState): Promise<IdeaTreeUiState> {
    const body = serializeIdeaTreeState(state);
    const res = await this.http.put<IdeaTreeStateResponse>(
      "/settings/idea-tree",
      body
    );
    return normalizeIdeaTreeState(res.data);
  }
}
