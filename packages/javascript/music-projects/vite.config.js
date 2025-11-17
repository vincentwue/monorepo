
import react from "@vitejs/plugin-react"
import path from "node:path"
import { defineConfig } from "vite"

export default defineConfig({
    envDir: path.resolve(__dirname, "../.."),
    plugins: [react()],
    resolve: {
        alias: {
            "@": path.resolve(__dirname, "src"),
            // "@monorepo/auth": path.resolve(__dirname, "../../packages/javascript/auth/src/index.ts"),
        },
    },
    server: {
        host: "0.0.0.0",
        port: 5179,
    },
    preview: {
        host: "0.0.0.0",
        port: 4179,
    },
})
