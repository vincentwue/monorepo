import path from "node:path";
import { fileURLToPath } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [react()],
  envDir: path.resolve(__dirname, "../../.."),
  resolve: {
    alias: [
      {
        find: /^@ideas\/tree-client$/,
        replacement: path.resolve(
          __dirname,
          "../../../packages/javascript/ideas-tree-client/src/index.ts"
        ),
      },
      {
        find: /^@monorepo\/layout$/,
        replacement: path.resolve(
          __dirname,
          "../../../packages/javascript/layout/src/index.ts"
        ),
      },
      {
        find: /^@monorepo\/topbar-layout$/,
        replacement: path.resolve(
          __dirname,
          "../../../packages/javascript/topbar-layout/src/index.ts"
        ),
      },
    ],
  },
  server: {
    host: "0.0.0.0",
    port: 5174,
  },
});
