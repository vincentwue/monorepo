import react from "@vitejs/plugin-react"
import { resolve } from "path"
import { defineConfig } from "vite"

export default defineConfig({
    root: "examples",
    plugins: [react()],
    resolve: {
        alias: {
            "@monorepo/auth": resolve(__dirname, "src"),
        },
    },
    server: {
        port: 5173,
        host: "0.0.0.0",
    },
    preview: {
        port: 5174,
    },
    test: {
        root: __dirname,
        globals: true,
        environment: "jsdom",
    },
})
