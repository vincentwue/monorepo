from __future__ import annotations

import os
from typing import List

from copy_actions import gather_signature_lines


class CopyMetricsMixin:
    CONTEXT_LINES_PER_FILE = 18

    def _update_copy_line_metrics(self) -> None:
        if not getattr(self, "copy_line_labels", None):
            return
        metrics = {
            "selected": self._estimate_selected_line_count(),
            "context": self._estimate_context_line_count(),
            "signatures": self._estimate_signature_line_count(),
        }
        for key, value in metrics.items():
            label = self.copy_line_labels.get(key)
            if label:
                label.setText(f"{value} lines")
        update_stats = getattr(self, "_update_preview_stats", None)
        if callable(update_stats):
            update_stats()

    def _estimate_selected_line_count(self) -> int:
        total = 0
        for path in self.selected_paths:
            count = self._line_count(path)
            if count:
                total += count
        return total

    def _estimate_context_line_count(self) -> int:
        if not self.context_candidate_files:
            return 0
        matches = [path for path in self.context_candidate_files if os.path.isfile(path)]
        return len(matches) * self.CONTEXT_LINES_PER_FILE

    def _estimate_signature_line_count(self) -> int:
        total = 0
        for path in self.selected_paths:
            if not path.endswith((".py", ".ts", ".tsx")):
                continue
            lines = self.get_signature_preview_lines(path)
            if not lines:
                continue
            total += len(lines) + 3
        return total

    def get_signature_preview_lines(self, path: str) -> List[str]:
        cache = getattr(self, "signature_preview_cache", None)
        if cache is None:
            cache = {}
            self.signature_preview_cache = cache
        if path in cache:
            return cache[path]
        lines = gather_signature_lines(path)
        cache[path] = lines
        return lines
