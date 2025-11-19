from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[7]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from packages.python.ableton_cues.generation import ensure_refs

__all__ = ["ensure_refs"]
