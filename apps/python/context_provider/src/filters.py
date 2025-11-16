from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterable, Sequence

from utils import log


@dataclass(slots=True)
class FilterResult:
    visible_paths: list[str]
    matched_paths: set[str]
    matched_files: set[str]


def apply_filters(
    all_paths: Sequence[str],
    file_paths: Sequence[str],
    path_terms: Iterable[str],
    file_terms: Iterable[str],
    parent_lookup: dict[str, str | None],
    file_cache: dict[str, str],
) -> FilterResult:
    """
    Compute which paths should remain visible after applying path and in-file filters.
    """
    normalized_path_terms = [term.lower() for term in path_terms if term]
    normalized_file_terms = [term.lower() for term in file_terms if term]

    matched: set[str] = set()
    if normalized_path_terms:
        for path in all_paths:
            lower_path = path.lower()
            if any(term in lower_path for term in normalized_path_terms):
                matched.add(path)
                matched.update(_ancestors(path, parent_lookup))
    else:
        matched.update(all_paths)

    if normalized_file_terms:
        matched = _filter_by_file_content(
            normalized_file_terms, matched or set(all_paths), file_paths, parent_lookup, file_cache
        )

    visible_paths = [path for path in all_paths if path in matched]
    matched_files = {path for path in file_paths if path in matched}
    log(f"[filters] visible={len(visible_paths)} matched_files={len(matched_files)}")
    return FilterResult(visible_paths=visible_paths, matched_paths=matched, matched_files=matched_files)


def _ancestors(path: str, parent_lookup: dict[str, str | None]) -> set[str]:
    ancestors: set[str] = set()
    current = path
    while True:
        parent = parent_lookup.get(current)
        if not parent or parent in ancestors:
            break
        ancestors.add(parent)
        current = parent
    return ancestors


def _filter_by_file_content(
    search_terms: list[str],
    current_matches: set[str],
    file_paths: Sequence[str],
    parent_lookup: dict[str, str | None],
    file_cache: dict[str, str],
) -> set[str]:
    matched: set[str] = set()
    total_files = 0
    inspected_files = 0

    for path in file_paths:
        if current_matches and path not in current_matches:
            continue
        total_files += 1
        try:
            content = file_cache.get(path)
            if content is None:
                with open(path, "r", encoding="utf-8", errors="ignore") as handle:
                    content = handle.read()
                    file_cache[path] = content
            inspected_files += 1
            lowered_lines = content.splitlines()
            if any(any(term in line.lower() for term in search_terms) for line in lowered_lines):
                matched.add(path)
                matched.update(_ancestors(path, parent_lookup))
        except OSError as exc:
            log(f"[filters] unable to read {path}: {exc}")

    log(f"[filters] in-file search terms={len(search_terms)} inspected={inspected_files}/{total_files}")
    return matched
