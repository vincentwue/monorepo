import react from "@vitejs/plugin-react";
import path from "path";
import { defineConfig } from "vite";

export default defineConfig({
  root: "examples",
  plugins: [react()],
  resolve: {
    alias: {
      "@monorepo/tree": path.resolve(__dirname, "src"),
    },
  },
  server: {
    port: 5173,
  },
  test: {
    root: __dirname, // ✅ ensures Vitest looks in /src instead of /examples
    globals: true,
    environment: "node",
    include: ["src/**/*.{test,spec}.ts"],
  },
});
