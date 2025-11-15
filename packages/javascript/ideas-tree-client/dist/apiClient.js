import axios from "axios";
/**
 * Example usage in a web app:
 *
 * ```ts
 * const client = new IdeasApiClient({ baseUrl: import.meta.env.VITE_API_URL });
 * const children = await client.listChildren(parentId);
 * ```
 */
export class IdeasApiClient {
    http;
    constructor(options) {
        const baseUrl = options.baseUrl.replace(/\/$/, "");
        this.http = axios.create({
            baseURL: baseUrl,
            withCredentials: true,
        });
    }
    async listChildren(parentId) {
        const params = {};
        if (parentId != null) {
            params.parent_id = parentId;
        }
        const res = await this.http.get("/ideas/children", { params });
        return res.data;
    }
    async createChild(parentId, title, note) {
        const params = {};
        if (parentId != null) {
            params.parent_id = parentId;
        }
        const body = { title };
        if (note !== undefined) {
            body.note = note;
        }
        const res = await this.http.post("/ideas/children", body, { params });
        return res.data;
    }
    async moveNode(nodeId, newParentId) {
        const body = {
            new_parent_id: newParentId,
        };
        const res = await this.http.post(`/ideas/nodes/${encodeURIComponent(nodeId)}/move`, body);
        return res.data;
    }
    async reorderNode(nodeId, direction, targetRank) {
        const body = {
            direction,
        };
        if (typeof targetRank === "number") {
            body.target_rank = targetRank;
        }
        const res = await this.http.post(`/ideas/nodes/${encodeURIComponent(nodeId)}/reorder`, body);
        return res.data;
    }
}
