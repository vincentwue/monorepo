import react from "@vitejs/plugin-react";
import path from "path";
import { defineConfig } from "vite";

export default defineConfig({
  root: "examples",
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
      "@monorepo/store": path.resolve(__dirname, "../store/src"),
      "@monorepo/mongo-explorer": path.resolve(
        __dirname,
        "../mongo-explorer/src"
      ),
    },
  },
  server: { port: 5173 },
  build: { outDir: "../dist", emptyOutDir: true },
});
