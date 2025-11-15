import os
from utils import log


def apply_combined_filter(app):
    """Applies both path and in-file filters."""
    path_query = app.search_var.get().strip().lower()
    file_query = app.file_search_var.get().strip().lower()
    log(f"Applying filters: path='{path_query}' | in-file='{file_query}'")

    path_keywords = [k for k in path_query.split() if k]
    file_keywords = [k for k in file_query.split() if k]

    matched = set()

    # Path-based matches
    for path, row, depth in app.row_widgets:
        lower_path = path.lower()
        if not path_keywords or all(k in lower_path for k in path_keywords):
            matched.add(path)
            for i in range(1, len(path.split(os.sep))):
                matched.add(os.sep.join(path.split(os.sep)[:i]))

    # Combine with in-file matches if specified
    if file_keywords:
        matched = apply_in_file_filter(app, file_keywords, matched)

    _show_matched(app, matched)


def apply_in_file_filter(app, keywords, path_matches):
    """Refines path matches by in-file keyword search."""
    log(f"Running in-file search for: {keywords}")
    folder = app.path_var.get()
    matched = set()
    total = 0
    matched_files = 0

    for path, row, depth in app.row_widgets:
        if not os.path.isfile(path):
            continue
        if path_matches and path not in path_matches:
            continue
        total += 1
        try:
            if path in app.file_cache:
                content = app.file_cache[path]
            else:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    app.file_cache[path] = content
            lc = content.lower()
            if all(k in lc for k in keywords):
                matched.add(path)
                matched_files += 1
                # include parent directories
                parts = path.split(os.sep)
                for i in range(1, len(parts)):
                    matched.add(os.sep.join(parts[:i]))
        except Exception as e:
            log(f"Could not read {path}: {e}")

    log(f"In-file search done. Matched {matched_files}/{total} files.")
    return matched

from file_tree import build_ascii_from_paths
from utils import update_text_widget

from file_tree import build_ascii_from_paths
from utils import update_text_widget, log


from file_tree import build_ascii_from_paths
from utils import update_text_widget, log
import os


def _show_matched(app, matched):
    """Show/hide rows based on matched set and update ASCII tree overview dynamically."""
    visible = 0
    visible_paths = []

    for path, row, depth in app.row_widgets:
        is_visible = (not matched) or (path in matched)
        if is_visible:
            row.grid()
            visible += 1
            visible_paths.append(path)
        else:
            row.grid_remove()

    log(f"Visible rows: {visible}/{len(app.row_widgets)}")

    # --- Update right-side ASCII overview dynamically
    try:
        if hasattr(app, "ascii_text"):
            root_folder = app.path_var.get().strip()
            if visible_paths:
                # normalize to relpaths for ASCII renderer
                normalized = [
                    os.path.relpath(p, root_folder) if p.startswith(root_folder) else p
                    for p in visible_paths
                ]
                ascii_output = build_ascii_from_paths(root_folder, visible_paths)
                update_text_widget(app.ascii_text, ascii_output)
                log(f"[ASCII-DEBUG] Refreshed overview ({len(visible_paths)} visible paths)")
            else:
                update_text_widget(app.ascii_text, "(no results)")
                log("[ASCII-DEBUG] No visible paths -> cleared overview")
        if hasattr(app, "update_path_table"):
            app.update_path_table(visible_paths)
    except Exception as e:
        log(f"[ERROR updating ASCII tree] {e}")
