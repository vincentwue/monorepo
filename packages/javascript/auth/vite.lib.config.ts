import react from "@vitejs/plugin-react"
import { resolve } from "path"
import { defineConfig } from "vite"

export default defineConfig({
    plugins: [react()],
    envDir: __dirname,
    build: {
        sourcemap: true,
        lib: {
            entry: resolve(__dirname, "src/index.ts"),
            name: "MonorepoAuth",
            formats: ["es", "cjs"],
            fileName: (format) => {
                if (format === "es") return "index.js"
                if (format === "cjs") return "index.cjs"
                return `index.${format}.js`
            },
        },
        rollupOptions: {
            external: ["react", "react-dom", "react/jsx-runtime", "react-router-dom", "axios"],
            output: {
                globals: {
                    react: "React",
                    "react-dom": "ReactDOM",
                    "react/jsx-runtime": "ReactJSXRuntime",
                    "react-router-dom": "ReactRouterDOM",
                    axios: "axios",
                },
            },
        },
    },
})
