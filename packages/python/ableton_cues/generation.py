from __future__ import annotations

from pathlib import Path
from typing import Tuple

import numpy as np

try:
    from cue_library import CueLibrary, end_cue, start_cue, stop_cue
    from cue_library.constants import DEFAULT_REF_DIR, DEFAULT_SAMPLE_RATE
    from cue_library.io import stereo_to_pcm, to_stereo
except ImportError:  # pragma: no cover - fallback for workspace layout
    from packages.python.cue_library import CueLibrary, end_cue, start_cue, stop_cue
    from packages.python.cue_library.constants import DEFAULT_REF_DIR, DEFAULT_SAMPLE_RATE
    from packages.python.cue_library.io import stereo_to_pcm, to_stereo

FS = DEFAULT_SAMPLE_RATE
REF_DIR = DEFAULT_REF_DIR
START_NAME = "start"
END_NAME = "end"


def mk_start_cue() -> np.ndarray:
    return start_cue(FS)


def mk_end_cue() -> np.ndarray:
    return end_cue(FS)


def ensure_refs(ref_dir: str | Path | None = None) -> Tuple[str, str, np.ndarray, np.ndarray, bytes, bytes]:
    target_dir = Path(ref_dir) if ref_dir else Path(REF_DIR)
    lib = CueLibrary(sample_rate=FS, peak_db=0.0)
    refs = lib.ensure_primary_references(target_dir=target_dir)
    start_stereo = to_stereo(start_cue(FS), peak_db=0.0)
    end_stereo = to_stereo(end_cue(FS), peak_db=0.0)
    start_pcm = stereo_to_pcm(start_stereo)
    end_pcm = stereo_to_pcm(end_stereo)
    return (
        str(refs["start"]),
        str(refs["end"]),
        start_stereo,
        end_stereo,
        start_pcm,
        end_pcm,
    )


def mk_stop_unique(total_dur: float = 1.2, seed: int | None = None) -> np.ndarray:
    return stop_cue(total_dur=total_dur, seed=seed, fs=FS)


def ensure_stop_ref(
    filename: str = "stop.wav",
    *,
    ref_dir: str | Path | None = None,
    seed: int | None = None,
):
    target_dir = Path(ref_dir) if ref_dir else Path(REF_DIR)
    lib = CueLibrary(sample_rate=FS, peak_db=0.0)
    path = lib.ensure_stop_reference(filename=filename, target_dir=target_dir, seed=seed)
    stereo = to_stereo(stop_cue(seed=seed, fs=FS), peak_db=0.0)
    return str(path), stereo


__all__ = ["ensure_refs", "mk_stop_unique", "ensure_stop_ref"]
