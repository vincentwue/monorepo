import os
import re
from utils import log


def copy_selected(app):
    folder = app.path_var.get()
    included = sorted(app.selected_paths)
    content_files = [p for p in included if os.path.isfile(p)]

    log(f"Copy requested. Included={len(included)}, WithContent={len(content_files)}")

    if not folder:
        app.show_info("Please choose a folder first.")
        return
    if not included:
        app.show_info("No paths selected.")
        return

    output = [f"[ROOT] {folder}"]
    for path in included:
        rel = os.path.relpath(path, folder)
        output.append(rel)

    if content_files:
        output.append("\n" + "=" * 60 + "\nFILE CONTENTS:\n")
        for p in content_files:
            rel = os.path.relpath(p, folder)
            output.append(f"\n--- {rel} ---\n")
            try:
                with open(p, "r", encoding="utf-8", errors="ignore") as f:
                    output.append(f.read())
            except Exception as e:
                output.append(f"[ERROR reading {rel}: {e}]")

    text = "\n".join(output)
    total_lines = text.count("\n") + 1

    app.clipboard_clear()
    app.clipboard_append(text)
    app.update()

    msg = (
        f"Copied {len(included)} items; {len(content_files)} files with contents "
        f"- total lines: {total_lines}"
    )
    app.show_info(msg, duration=6)
    log(msg)
    app.update_result_preview(text, "Copy Selected")


def copy_context(app):
    """Copy only matched snippets from in-file search."""
    query = app.file_search_var.get().strip()
    if not query:
        app.show_info("No in-file search specified.")
        return
    folder = app.path_var.get()
    if not folder:
        app.show_info("Please choose a folder first.")
        return

    log(f"Copy Context triggered for '{query}'")
    keywords = [k.lower() for k in query.split() if k]
    output = []
    total_matches = 0

    for path, row, depth in app.row_widgets:
        if not os.path.isfile(path):
            continue
        try:
            content = app.file_cache.get(path)
            if not content:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
            lower = content.lower()
            if all(k in lower for k in keywords):
                total_matches += 1
                rel = os.path.relpath(path, folder)
                output.append(f"\n--- {rel} ---\n")
                lines = content.splitlines()
                for i, line in enumerate(lines):
                    if any(k in line.lower() for k in keywords):
                        start = max(0, i - 8)
                        end = min(len(lines), i + 8)
                        snippet = lines[start:end]
                        for j in range(i, 0, -1):
                            if "def " in lines[j] or "function " in lines[j] or "class " in lines[j]:
                                snippet.insert(0, f"... {lines[j].strip()} ...")
                                break
                        output.append("\n".join(snippet))
                        output.append("\n" + "-" * 60)
                        break
        except Exception as e:
            log(f"Could not extract context from {path}: {e}")

    if not output:
        app.show_info("No files contain the search string.")
        return

    text = "\n".join(output)
    total_lines = text.count("\n") + 1

    app.clipboard_clear()
    app.clipboard_append(text)
    app.update()

    msg = f"Copied context from {total_matches} files - total lines: {total_lines}"
    app.show_info(msg, duration=6)
    log(msg)
    app.update_result_preview(text, "Copy Context")


def copy_signatures(app):
    """
    Copy only imports, functions, class signatures, and Redux-style reducers/thunks
    from selected .py and .ts files.
    """
    folder = app.path_var.get()
    if not folder:
        app.show_info("Please choose a folder first.")
        return

    included_files = [
        p for p in sorted(app.selected_paths)
        if p.endswith(".py") or p.endswith(".ts") or p.endswith(".tsx")
    ]

    if not included_files:
        app.show_info("No Python or TypeScript files selected.")
        return

    log(f"CopySignatures: scanning {len(included_files)} files")

    output = [f"[ROOT] {folder}", "\n" + "=" * 60 + "\nSIGNATURES / STRUCTURE\n"]
    total_matches = 0
    total_lines = 0

    # -------------------------------
    # Regex patterns
    # -------------------------------

    PY_PATTERNS = [
        re.compile(r"^\s*(?:from\s+\S+\s+import\s+\S+|import\s+\S+)", re.MULTILINE),
        re.compile(r"^\s*(?:async\s+)?def\s+\w+\s*\(.*?\)\s*:", re.MULTILINE),
        re.compile(r"^\s*class\s+\w+", re.MULTILINE),
    ]

    TS_PATTERNS = [
        # imports
        re.compile(r"^\s*import\s+.*?from\s+['\"].*?['\"]\s*;?", re.MULTILINE),
        # function declarations
        re.compile(r"^\s*(?:export\s+)?(?:async\s+)?function\s+\w+\s*\(.*?\)\s*[{;]?", re.MULTILINE),
        # arrow functions assigned to const/let
        re.compile(r"^\s*(?:const|let)\s+\w+\s*=\s*(?:async\s*)?\(.*?\)\s*=>", re.MULTILINE),
        # class declarations
        re.compile(r"^\s*(?:export\s+)?class\s+\w+", re.MULTILINE),
        # object-literal methods (Redux reducers)
        re.compile(r"^\s*\w+\s*\([^)]*\)\s*{", re.MULTILINE),
    ]

    for path in included_files:
        rel = os.path.relpath(path, folder)
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            patterns = PY_PATTERNS if path.endswith(".py") else TS_PATTERNS
            matches = []

            for pat in patterns:
                for m in pat.findall(content):
                    matches.append(m.strip())

            if matches:
                output.append(f"\n--- {rel} ---\n")
                output.extend(matches)
                output.append("\n" + "-" * 60)
                total_matches += len(matches)
                total_lines += sum(m.count("\n") + 1 for m in matches)

        except Exception as e:
            log(f"[copy_signatures] Error reading {rel}: {e}")

    if not total_matches:
        app.show_info("No signatures found.")
        return

    text = "\n".join(output)
    app.clipboard_clear()
    app.clipboard_append(text)
    app.update()

    msg = (
        f"Copied {len(included_files)} files - {total_matches} signatures, "
        f"{total_lines} total lines"
    )
    app.show_info(msg, duration=6)
    log(msg)
    app.update_result_preview(text, "Copy Signatures")
