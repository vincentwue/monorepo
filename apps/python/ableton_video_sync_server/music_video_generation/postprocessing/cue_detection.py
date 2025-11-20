from __future__ import annotations

import sys
from pathlib import Path

# Similar trick as in primary_cue_service: make sure monorepo packages are used.

REPO_ROOT = Path(__file__).resolve().parents[6]
PKG_ROOT = REPO_ROOT / "packages" / "python"

for p in (PKG_ROOT, REPO_ROOT):
    sp = str(p)
    if sp not in sys.path:
        sys.path.insert(0, sp)

# Now import the local cue_detection package unambiguously.
from cue_detection import (  # type: ignore[import]
    gather_reference_library,
    compute_matches,
    build_segments,
    find_all_matches,
)

__all__ = ["gather_reference_library", "compute_matches", "build_segments", "find_all_matches"]
