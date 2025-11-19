from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[6]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

try:
    from cue_runtime import AudioOutputSelector
except ImportError:  # pragma: no cover - workspace fallback
    from packages.python.cue_runtime import AudioOutputSelector

__all__ = ["AudioOutputSelector"]
