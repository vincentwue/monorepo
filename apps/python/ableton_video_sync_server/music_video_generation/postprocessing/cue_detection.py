from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[6]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from packages.python.ableton_cues.detection import (
    gather_reference_library,
    compute_matches,
    build_segments,
    find_all_matches,
)

__all__ = ["gather_reference_library", "compute_matches", "build_segments", "find_all_matches"]
