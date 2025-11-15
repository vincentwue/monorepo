import os
from tkinter import ttk
from utils import log


def build_tree(app, folder, ignore_patterns):
    """Recursively build the tree UI."""
    for w in app.inner_frame.winfo_children():
        w.destroy()
    app.row_widgets.clear()
    app.all_paths.clear()
    app.file_cache.clear()

    def add_node(base_path, depth=0):
        try:
            entries = sorted(os.listdir(base_path))
        except (PermissionError, FileNotFoundError) as e:
            log(f"Skipping {base_path}: {e}")
            return

        for name in entries:
            full_path = os.path.join(base_path, name)
            if any(ign in full_path for ign in ignore_patterns):
                log(f"Ignored: {full_path}")
                continue

            is_dir = os.path.isdir(full_path)
            row = ttk.Frame(app.inner_frame)
            row.grid(sticky="w", padx=depth * 20, pady=1)
            row.path = full_path
            app.all_paths.append(full_path)

            ttk.Label(row, text=name).pack(side="left")

            app.row_widgets.append((full_path, row, depth))

            if is_dir:
                add_node(full_path, depth + 1)

    log(f"Rendering tree for {folder}")
    add_node(folder)
    log(f"Tree rendering complete. {len(app.all_paths)} total paths.")


def build_ascii_tree_text(folder, ignore_patterns):
    """Return a box-drawn ASCII tree string for the given folder."""
    BOX_LAST = "└── "
    BOX_MID = "├── "
    BOX_PIPE = "│   "
    BOX_GAP = "    "

    def build_tree_lines(path: str, prefix: str = "", lines=None):
        if lines is None:
            lines = []
        try:
            with os.scandir(path) as it:
                entries = sorted(
                    it,
                    key=lambda e: (not e.is_dir(follow_symlinks=False), e.name.lower()),
                )
        except (PermissionError, FileNotFoundError):
            lines.append(prefix + "(access denied)")
            return lines

        for idx, entry in enumerate(entries):
            is_last = idx == len(entries) - 1
            branch = BOX_LAST if is_last else BOX_MID
            if any(ign in entry.path for ign in ignore_patterns):
                continue
            lines.append(f"{prefix}{branch}{entry.name}")
            if entry.is_dir(follow_symlinks=False) and not entry.is_symlink():
                next_prefix = prefix + (BOX_GAP if is_last else BOX_PIPE)
                build_tree_lines(entry.path, next_prefix, lines)
        return lines

    lines = [folder]
    lines.extend(build_tree_lines(folder))
    return "\n".join(lines)


def build_ascii_from_paths(root_folder: str, paths: list[str]) -> str:
    """
    Build an ASCII tree representation from a list of visible absolute or relative paths.
    """
    BOX_LAST = "└── "
    BOX_MID = "├── "
    BOX_PIPE = "│   "
    BOX_GAP = "    "

    tree = {}
    for path in sorted(paths):
        if os.path.isabs(path):
            rel = os.path.relpath(path, root_folder)
        else:
            rel = path
        if rel == ".":
            continue
        parts = rel.split(os.sep)
        node = tree
        for part in parts:
            node = node.setdefault(part, {})

    def walk(subtree, prefix=""):
        lines = []
        keys = sorted(subtree.keys())
        for idx, key in enumerate(keys):
            is_last = idx == len(keys) - 1
            branch = BOX_LAST if is_last else BOX_MID
            lines.append(f"{prefix}{branch}{key}")
            next_prefix = prefix + (BOX_GAP if is_last else BOX_PIPE)
            lines.extend(walk(subtree[key], next_prefix))
        return lines

    lines = [root_folder]
    lines.extend(walk(tree))
    return "\n".join(lines)
