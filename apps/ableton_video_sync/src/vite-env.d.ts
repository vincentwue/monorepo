/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_INGEST_API_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
