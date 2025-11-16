function safeRequire(name) {
  try {
    return require(name);
  } catch {
    return null;
  }
}

const forms = safeRequire("@tailwindcss/forms");
const typography = safeRequire("@tailwindcss/typography");

const sharedPreset = {
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        brand: "rgb(var(--brand) / <alpha-value>)",
        "brand-strong": "rgb(var(--brand-strong) / <alpha-value>)",
        bg: "rgb(var(--bg) / <alpha-value>)",
        card: "rgb(var(--card) / <alpha-value>)",
        surface: "rgb(var(--surface) / <alpha-value>)",
        muted: "rgb(var(--text-muted) / <alpha-value>)",
        text: "rgb(var(--text-primary) / <alpha-value>)",
        border: "rgb(var(--border-soft) / <alpha-value>)"
      },
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        display: ["var(--font-sans)", "system-ui", "sans-serif"]
      },
      backgroundImage: {
        "page-gradient": "var(--page-gradient)",
        "panel-gradient": "var(--panel-gradient)"
      },
      boxShadow: {
        glow: "0 25px 60px rgba(2, 6, 23, 0.7)"
      },
      borderRadius: {
        xl: "1.25rem"
      }
    }
  },
  plugins: [forms, typography].filter(Boolean)
};

module.exports = sharedPreset;
module.exports.default = sharedPreset;
