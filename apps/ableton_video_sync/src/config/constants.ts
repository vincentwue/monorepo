export const INGEST_API_BASE_URL =
  (typeof import.meta !== 'undefined' && import.meta.env?.VITE_INGEST_API_URL) || 'http://127.0.0.1:5050'
