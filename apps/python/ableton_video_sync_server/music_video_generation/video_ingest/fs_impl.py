from __future__ import annotations

import os
from pathlib import Path
from typing import List

from .utils import is_video


def scan_filesystem(base_path: Path | str) -> List[Path]:
    """Recursively scan a local filesystem directory for video files."""
    base = Path(base_path)
    if not base.exists():
        return []
    out: list[Path] = []
    for root, _dirs, files in os.walk(base):
        for name in files:
            p = Path(root) / name
            if is_video(p):
                out.append(p)
    return out


__all__ = ["scan_filesystem"]
