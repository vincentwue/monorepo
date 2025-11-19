from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[6]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

try:
    from cue_detection_service import PrimaryCueDetectionService
except ImportError:  # pragma: no cover - workspace fallback
    from packages.python.cue_detection_service import PrimaryCueDetectionService

__all__ = ["PrimaryCueDetectionService"]
