import sharedPreset from "@monorepo/design-system/tailwind-preset";
import type { Config } from "tailwindcss";

export default {
  content: [
    "./index.html",
    "./src/**/*.{ts,tsx}",
    "../../packages/javascript/auth/src/**/*.{ts,tsx}",
  ],
  presets: [sharedPreset],
} satisfies Config;
