import type { Config } from "tailwindcss";

// 🔧 Best-effort loader so missing plugins don't crash dev
function tryRequire(name: string) {
  try {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const m = require(name);
    console.debug("[tailwind] plugin loaded:", name); // LOG
    return m;
  } catch {
    console.warn("[tailwind] plugin missing, skipping:", name); // LOG
    return null;
  }
}

const forms = tryRequire("@tailwindcss/forms");
const typography = tryRequire("@tailwindcss/typography");

export default {
  content: [
    "./index.html",
    "./src/**/*.{ts,tsx,css}",
    "../../../packages/javascript/topbar-layout/src/**/*.{ts,tsx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        brand: "rgb(var(--brand) / <alpha-value>)",
        bg: "rgb(var(--bg) / <alpha-value>)",
        card: "rgb(var(--card) / <alpha-value>)",
      },
    },
  },
  plugins: [
    ...(forms ? [forms] : []),
    ...(typography ? [typography] : []),
  ],
} satisfies Config;
