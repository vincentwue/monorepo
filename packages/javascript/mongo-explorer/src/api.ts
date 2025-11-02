import { createApi, fetchBaseQuery } from "@reduxjs/toolkit/query/react";

export interface Connection {
  alias: string;
  uri: string;
}

// localStorage helpers
const STORAGE_KEY = "mongoConnections";
export function loadConnections(): Connection[] {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "[]");
  } catch {
    return [];
  }
}
export function saveConnections(conns: Connection[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(conns));
}

// --- Base setup ---
const baseQuery = fetchBaseQuery({
  baseUrl: "http://localhost:8010",
  prepareHeaders: (headers) => {
    headers.set("Content-Type", "application/json");
    return headers;
  },
});

export const mongoApi = createApi({
  reducerPath: "mongoApi",
  baseQuery,
  tagTypes: ["Connections", "Databases", "Collections"],
  endpoints: (build) => ({
    // --- Local-only connections (no backend) ---
    listDatabases: build.query<string[], string>({
      query: (alias) => {
        const conn = loadConnections().find((c) => c.alias === alias);
        if (!conn) throw new Error(`Unknown alias: ${alias}`);
        const params = new URLSearchParams({ uri: conn.uri });
        return `/mongo/databases?${params.toString()}`;
      },
      providesTags: ["Databases"],
    }),

    listCollections: build.query<string[], { alias: string; db: string }>({
      query: ({ alias, db }) => {
        const conn = loadConnections().find((c) => c.alias === alias);
        if (!conn) throw new Error(`Unknown alias: ${alias}`);
        const params = new URLSearchParams({ uri: conn.uri, db });
        return `/mongo/collections?${params.toString()}`;
      },
      providesTags: ["Collections"],
    }),

    // --- Collections from backend ---
    listCollections: build.query<string[], { alias: string; db: string }>({
      query: ({ alias, db }) => {
        const conn = loadConnections().find((c) => c.alias === alias);
        if (!conn) throw new Error(`Unknown alias: ${alias}`);
        return `/mongo/collections?alias=${encodeURIComponent(alias)}&db=${encodeURIComponent(db)}`;
      },
      providesTags: ["Collections"],
    }),
  }),
});

export const {
  useListConnectionsQuery,
  useListDatabasesQuery,
  useListCollectionsQuery,
} = mongoApi;
