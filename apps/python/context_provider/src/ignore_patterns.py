IGNORE_PATTERNS = [
    # --- Dependency / virtual envs ---
    "node_modules",
    ".venv",
    # "env",
    "__pycache__",
    ".python-version",

    # --- Build / cache / dist ---
    "dist",
    "build",
    ".vite",
    ".turbo",
    ".parcel-cache",
    ".next",
    ".cache",
    ".coverage",
    "coverage",

    # --- IDE / system ---
    ".idea",
    ".vscode",
    ".git",
    ".DS_Store",

    # --- Frontend generated assets ---
    "assets",
    "public/vite.svg",
    "*.ico",
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.svg",
    "*.webp",

    # --- Test & report outputs ---
    "playwright-report",
    "test-results",
    "tests/e2e",
    "__tests__",
    "*.spec.ts",
    "*.test.tsx",

    # --- Scripts and temp data you rarely need in context dumps ---
    "scripts/context_provider",
    "*.pyc",
    "*.pyo",
    "*.log",

    # --- Configs and lockfiles (rarely relevant for structure) ---
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "uv.lock",
    "pyproject.toml",
    "requirements.txt",
    "tsconfig.node.json",
    "tsconfig.app.json",
    "postcss.config.js",
    "tailwind.config.js",
    "vite.config.ts",
    "eslint.config.js",
    # ".env",

    # --- Docs / markdown exports ---
    "README.md",
    "docs/learn.txt",
]
