from __future__ import annotations

try:
    from cue_detection import *  # noqa: F401,F403
except ImportError:  # pragma: no cover - workspace fallback
    from packages.python.cue_detection import *  # type: ignore # noqa: F401,F403
