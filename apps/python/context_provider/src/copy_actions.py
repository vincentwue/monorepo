import ast
import os
import re

from utils import log


def copy_selected(app):
    folder = app.current_folder
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
        for path in content_files:
            rel = os.path.relpath(path, folder)
            output.append(f"\n--- {rel} ---\n")
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as handle:
                    output.append(handle.read())
            except OSError as exc:
                output.append(f"[ERROR reading {rel}: {exc}]")

    text = "\n".join(output)
    total_lines = text.count("\n") + 1

    app.set_clipboard_text(text)
    msg = (
        f"Copied {len(included)} items; {len(content_files)} files with contents "
        f"- total lines: {total_lines}"
    )
    app.show_info(msg, duration=6)
    log(msg)
    app.update_result_preview(text, "Copy Selected")


def copy_context(app):
    """Copy only matched snippets from in-file search."""
    terms = app.get_infile_filter_terms()
    if not terms:
        app.show_info("No in-file include strings specified.")
        return
    folder = app.current_folder
    if not folder:
        app.show_info("Please choose a folder first.")
        return

    log(f"Copy Context triggered for '{', '.join(terms)}'")
    keywords = [t.lower() for t in terms]
    output: list[str] = []
    total_matches = 0

    for path in app.file_paths:
        try:
            content = app.file_cache.get(path)
            if not content:
                with open(path, "r", encoding="utf-8", errors="ignore") as handle:
                    content = handle.read()
                    app.file_cache[path] = content
            lines = content.splitlines()
            match_index = _find_keyword_line(lines, keywords)
            if match_index is None:
                continue
            total_matches += 1
            rel = os.path.relpath(path, folder)
            output.append(f"\n--- {rel} ---\n")
            start = max(0, match_index - 8)
            end = min(len(lines), match_index + 8)
            snippet = lines[start:end]
            for j in range(match_index, -1, -1):
                stripped = lines[j].strip()
                if stripped.startswith(("def ", "class ", "function ")):
                    snippet.insert(0, f"... {stripped} ...")
                    break
            output.append("\n".join(snippet))
            output.append("\n" + "-" * 60)
        except OSError as exc:
            log(f"Could not extract context from {path}: {exc}")

    if not output:
        app.show_info("No files contain the search string.")
        return

    text = "\n".join(output)
    total_lines = text.count("\n") + 1

    app.set_clipboard_text(text)
    msg = f"Copied context from {total_matches} files - total lines: {total_lines}"
    app.show_info(msg, duration=6)
    log(msg)
    app.update_result_preview(text, "Copy Context")


def _find_keyword_line(lines: list[str], keywords: list[str]) -> int | None:
    for idx, line in enumerate(lines):
        lowered = line.lower()
        if any(keyword in lowered for keyword in keywords):
            return idx
    return None


def copy_signatures(app):
    """
    Copy an overview of imports, classes, functions, and React-style components
    from selected .py/.ts/.tsx files.
    """
    folder = app.current_folder
    if not folder:
        app.show_info("Please choose a folder first.")
        return

    included_files = [
        path
        for path in sorted(app.selected_paths)
        if path.endswith((".py", ".ts", ".tsx"))
    ]

    if not included_files:
        app.show_info("No Python or TypeScript files selected.")
        return

    log(f"CopySignatures: scanning {len(included_files)} files")

    output = [f"[ROOT] {folder}", "\n" + "=" * 60 + "\nSIGNATURES / STRUCTURE\n"]
    total_matches = 0
    total_lines = 0

    for path in included_files:
        rel = os.path.relpath(path, folder)
        matches = []
        if hasattr(app, "get_signature_preview_lines"):
            matches = app.get_signature_preview_lines(path) or []
        if not matches:
            matches = gather_signature_lines(path)
        if not matches:
            continue

        output.append(f"\n--- {rel} ---\n")
        output.extend(matches)
        output.append("\n" + "-" * 60)
        total_matches += len(matches)
        total_lines += sum(match.count("\n") + 1 for match in matches)

    if not total_matches:
        app.show_info("No signatures found.")
        return

    text = "\n".join(output)
    app.set_clipboard_text(text)

    msg = (
        f"Copied {len(included_files)} files - {total_matches} signatures, "
        f"{total_lines} total lines"
    )
    app.show_info(msg, duration=6)
    log(msg)
    app.update_result_preview(text, "Copy Signatures")


def gather_signature_lines(path: str) -> list[str]:
    """Return signature lines for a Python/TypeScript file."""
    try:
        if path.endswith(".py"):
            return _extract_python_signatures(path)
        if path.endswith((".ts", ".tsx")):
            return _extract_typescript_signatures(path)
    except OSError as exc:
        log(f"[copy_signatures] Error reading {path}: {exc}")
    return []


def _extract_python_signatures(path: str) -> list[str]:
    with open(path, "r", encoding="utf-8", errors="ignore") as handle:
        source = handle.read()
    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError as exc:
        log(f"[copy_signatures] SyntaxError in {path}: {exc}")
        return []

    signatures: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            signatures.append(_format_import(node))
        elif isinstance(node, ast.ImportFrom):
            signatures.append(_format_import_from(node))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            signatures.append(_format_function(node))
        elif isinstance(node, ast.ClassDef):
            signatures.extend(_format_class(node))
    return [sig for sig in signatures if sig]


def _format_import(node: ast.Import) -> str:
    parts = []
    for alias in node.names:
        if alias.asname:
            parts.append(f"{alias.name} as {alias.asname}")
        else:
            parts.append(alias.name)
    return f"import {', '.join(parts)}"


def _format_import_from(node: ast.ImportFrom) -> str:
    module = node.module or ""
    parts = []
    for alias in node.names:
        if alias.asname:
            parts.append(f"{alias.name} as {alias.asname}")
        else:
            parts.append(alias.name)
    return f"from {module} import {', '.join(parts)}"


def _format_class(node: ast.ClassDef) -> list[str]:
    bases = [_safe_unparse(base) for base in node.bases]
    decorators = [_safe_unparse(dec) for dec in node.decorator_list]
    header = f"class {node.name}"
    if bases:
        header += f"({', '.join(bases)})"
    if decorators:
        header += f" [decorators: {', '.join(decorators)}]"
    doc = _first_line_doc(node)
    if doc:
        header += f"  # {doc}"
    lines = [header]
    for child in node.body:
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            lines.append("    " + _format_function(child))
    return lines


def _format_function(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    signature = _format_arguments(node.args)
    result = f"{prefix} {node.name}({signature})"
    if getattr(node, "returns", None):
        result += f" -> {_safe_unparse(node.returns)}"
    if node.decorator_list:
        decorators = ", ".join(_safe_unparse(dec) for dec in node.decorator_list)
        result += f" [decorators: {decorators}]"
    doc = _first_line_doc(node)
    if doc:
        result += f"  # {doc}"
    return result


def _format_arguments(args: ast.arguments) -> str:
    parts: list[str] = []
    positional = list(args.posonlyargs) + list(args.args)
    defaults = [None] * (len(positional) - len(args.defaults)) + list(args.defaults)
    for arg, default in zip(positional, defaults):
        text = _format_arg(arg)
        if default is not None:
            text += f"={_safe_unparse(default)}"
        parts.append(text)
    if args.posonlyargs:
        parts.insert(len(args.posonlyargs), "/")
    if args.vararg:
        parts.append("*" + _format_arg(args.vararg))
    elif args.kwonlyargs:
        parts.append("*")
    for kw_arg, default in zip(args.kwonlyargs, args.kw_defaults):
        text = _format_arg(kw_arg)
        if default is not None:
            text += f"={_safe_unparse(default)}"
        parts.append(text)
    if args.kwarg:
        parts.append("**" + _format_arg(args.kwarg))
    return ", ".join(filter(None, parts))


def _format_arg(arg: ast.arg) -> str:
    text = arg.arg
    if arg.annotation:
        text += f": {_safe_unparse(arg.annotation)}"
    return text


def _first_line_doc(node: ast.AST) -> str | None:
    doc = ast.get_docstring(node, clean=True)
    if not doc:
        return None
    return doc.strip().splitlines()[0].strip()


def _safe_unparse(node: ast.AST) -> str:
    try:
        return ast.unparse(node)
    except Exception:
        return "..."


TS_INTERFACE_PATTERN = re.compile(r"^\s*(export\s+)?(interface|type|enum)\s+([\w$]+)")
TS_CLASS_PATTERN = re.compile(r"^\s*(export\s+)?class\s+([\w$]+)")
TS_FUNCTION_PATTERN = re.compile(r"^\s*(export\s+)?(?:async\s+)?function\s+([\w$]+)\s*\(")
TS_CONST_PATTERN = re.compile(r"^\s*(export\s+)?(const|let|var)\s+([\w$]+)\s*=")


def _extract_typescript_signatures(path: str) -> list[str]:
    with open(path, "r", encoding="utf-8", errors="ignore") as handle:
        text = handle.read()
    lines = text.splitlines()
    signatures: list[str] = []
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if not stripped:
            i += 1
            continue
        if stripped.startswith("import "):
            signatures.append(stripped)
            i += 1
            continue
        if TS_INTERFACE_PATTERN.match(stripped):
            signature, i = _collect_ts_signature(lines, i)
            signatures.append(signature)
            i += 1
            continue
        if TS_CLASS_PATTERN.match(stripped):
            signature, i = _collect_ts_signature(lines, i)
            signatures.append(signature)
            i += 1
            continue
        if TS_FUNCTION_PATTERN.match(stripped):
            signature, i = _collect_ts_signature(lines, i)
            signatures.append(signature)
            i += 1
            continue
        match = TS_CONST_PATTERN.match(stripped)
        if match:
            name = match.group(3)
            exported = bool(match.group(1))
            if exported or name[:1].isupper() or name.startswith("use"):
                signature, i = _collect_ts_signature(lines, i)
                signatures.append(signature)
                i += 1
                continue
        i += 1
    return signatures


def _collect_ts_signature(lines: list[str], start_index: int) -> tuple[str, int]:
    collected: list[str] = []
    i = start_index
    paren_depth = 0
    arrow_seen = False
    brace_seen = False

    while i < len(lines):
        part = lines[i].strip()
        collected.append(part)
        paren_depth += part.count("(") - part.count(")")
        if "=>" in part:
            arrow_seen = True
        if "{" in part:
            brace_seen = True
        if paren_depth <= 0 and (arrow_seen or brace_seen):
            break
        if paren_depth <= 0 and part.endswith(";"):
            break
        i += 1

    signature = " ".join(segment for segment in collected if segment)
    signature = re.sub(r"\s+", " ", signature).strip()
    return signature, i
