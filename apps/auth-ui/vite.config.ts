import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"
import { resolve } from "path"

export default defineConfig({
    envDir: __dirname,
    plugins: [react()],
    resolve: {
        alias: {
            "@": resolve(__dirname, "src"),
        },
    },
    server: {
        host: "0.0.0.0",
        port: 5173,
    },
    preview: {
        host: "0.0.0.0",
        port: 4173,
    },
})
