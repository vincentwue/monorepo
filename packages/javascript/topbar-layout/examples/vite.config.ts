import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  root: path.resolve(__dirname, "src"),
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5147,
  },
  preview: {
    host: "0.0.0.0",
    port: 5147,
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
      "@monorepo/topbar-layout": path.resolve(__dirname, "../src"),
    },
  },
});
