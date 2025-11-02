import path from "path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@monorepo": path.resolve(__dirname, "../../../packages/javascript"),
    },
  },
  optimizeDeps: {
    exclude: ["@monorepo/store", "@monorepo/mongo-explorer"],
  },
});
