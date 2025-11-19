from __future__ import annotations

try:
    from cue_detection_service import PrimaryCueDetectionService
except ImportError:  # pragma: no cover - workspace fallback
    from packages.python.cue_detection_service import PrimaryCueDetectionService

__all__ = ["PrimaryCueDetectionService"]
