/**
 * PostCSS pipeline to ensure Tailwind directives expand during dev/build.
 */
module.exports = {
  plugins: {
    tailwindcss: { config: "./tailwind.config.ts" },
  },
};
