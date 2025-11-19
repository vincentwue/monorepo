from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[6]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

try:
    from cue_player import CuePlayer, mk_barker_bpsk, to_stereo, unique_cue, fade, FS
except ImportError:  # pragma: no cover - workspace fallback
    from packages.python.cue_player import CuePlayer, mk_barker_bpsk, to_stereo, unique_cue, fade, FS

__all__ = ["CuePlayer", "mk_barker_bpsk", "to_stereo", "unique_cue", "fade", "FS"]
