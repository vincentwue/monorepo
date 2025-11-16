from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterable, Iterator, List

from utils import log


ASCII_LAST = "`-- "
ASCII_MID = "|-- "
ASCII_PIPE = "|   "
ASCII_GAP = "    "


@dataclass(slots=True)
class TreeEntry:
    """Lightweight representation of a filesystem node."""

    path: str
    name: str
    parent: str | None
    depth: int
    is_dir: bool


def gather_tree_entries(folder: str, ignore_patterns: Iterable[str]) -> List[TreeEntry]:
    """
    Walk the given folder and return TreeEntry rows honoring ignore patterns.
    """
    root = os.path.abspath(folder)
    entries: list[TreeEntry] = []
    for entry in _walk_tree(root, None, 0, list(ignore_patterns)):
        entries.append(entry)
    log(f"[tree] gathered {len(entries)} entries under {root}")
    return entries


def _walk_tree(
    current: str,
    parent: str | None,
    depth: int,
    ignore_patterns: list[str],
) -> Iterator[TreeEntry]:
    try:
        with os.scandir(current) as it:
            items = sorted(
                it,
                key=lambda e: (not e.is_dir(follow_symlinks=False), e.name.lower()),
            )
    except (PermissionError, FileNotFoundError) as exc:
        log(f"[tree] skipping {current}: {exc}")
        return

    for entry in items:
        full_path = entry.path
        if _should_ignore(full_path, ignore_patterns):
            log(f"[tree] ignored {full_path}")
            continue
        is_dir = entry.is_dir(follow_symlinks=False)
        yield TreeEntry(
            path=full_path,
            name=entry.name,
            parent=parent or os.path.abspath(current),
            depth=depth,
            is_dir=is_dir,
        )
        if is_dir:
            yield from _walk_tree(full_path, full_path, depth + 1, ignore_patterns)


def _should_ignore(path: str, patterns: Iterable[str]) -> bool:
    lower = path.lower()
    return any(pattern.lower() in lower for pattern in patterns)


def build_ascii_tree_text(folder: str, ignore_patterns: Iterable[str]) -> str:
    """Return a text tree for the entire folder."""

    def build_lines(path: str, prefix: str = "") -> list[str]:
        lines: list[str] = []
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
            full_path = entry.path
            if _should_ignore(full_path, ignore_patterns):
                continue
            is_last = idx == len(entries) - 1
            branch = ASCII_LAST if is_last else ASCII_MID
            lines.append(f"{prefix}{branch}{entry.name}")
            if entry.is_dir(follow_symlinks=False) and not entry.is_symlink():
                next_prefix = prefix + (ASCII_GAP if is_last else ASCII_PIPE)
                lines.extend(build_lines(full_path, next_prefix))
        return lines

    folder = os.path.abspath(folder)
    result = [folder]
    result.extend(build_lines(folder))
    return "\n".join(result)


def build_ascii_from_paths(root_folder: str, paths: list[str]) -> str:
    """
    Build an ASCII tree representation from a list of absolute or relative paths.
    """
    root = os.path.abspath(root_folder)
    tree: dict[str, dict] = {}
    for path in sorted(paths):
        absolute = path if os.path.isabs(path) else os.path.join(root, path)
        try:
            rel = os.path.relpath(absolute, root)
        except ValueError:
            rel = path
        if rel in (".", ""):
            continue
        parts = rel.split(os.sep)
        node = tree
        for part in parts:
            node = node.setdefault(part, {})

    def walk(subtree: dict[str, dict], prefix: str = "") -> list[str]:
        lines: list[str] = []
        keys = sorted(subtree.keys())
        for idx, key in enumerate(keys):
            is_last = idx == len(keys) - 1
            branch = ASCII_LAST if is_last else ASCII_MID
            lines.append(f"{prefix}{branch}{key}")
            next_prefix = prefix + (ASCII_GAP if is_last else ASCII_PIPE)
            lines.extend(walk(subtree[key], next_prefix))
        return lines

    result = [root]
    result.extend(walk(tree))
    return "\n".join(result)
