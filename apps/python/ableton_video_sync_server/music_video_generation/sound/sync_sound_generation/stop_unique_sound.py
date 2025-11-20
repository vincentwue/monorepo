from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[7]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

try:
    from cue_library import CueLibrary
except ImportError:  # workspace / monorepo layout
    from packages.python.cue_library import CueLibrary

_LIB = CueLibrary(peak_db=0.0)


def mk_stop_unique(total_dur: float = 1.2, seed: int | None = None):
    return _LIB.stop_cue(total_dur=total_dur, seed=seed)


def ensure_stop_ref(
    filename: str = "stop.wav",
    *,
    ref_dir: str | Path | None = None,
    seed: int | None = None,
):
    path = _LIB.ensure_stop_reference(filename=filename, target_dir=ref_dir, seed=seed)
    stereo = _LIB.to_stereo(_LIB.stop_cue(seed=seed))
    return str(path), stereo

__all__ = ["mk_stop_unique", "ensure_stop_ref"]
