import react from "@vitejs/plugin-react"
import { resolve } from "path"
import { defineConfig } from "vite"

export default defineConfig({
    root: __dirname,
    plugins: [react()],
    resolve: {
        alias: {
            "@mobile-tree-ui": resolve(__dirname, "../src"),
        },
    },
    server: {
        host: "0.0.0.0",
        port: 5176,
    },
})
