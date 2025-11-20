from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[7]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

try:
    from cue_library import CueLibrary
    from cue_library.constants import DEFAULT_REF_DIR
    from cue_library.io import stereo_to_pcm
except ImportError:  # workspace / monorepo layout
    from packages.python.cue_library import CueLibrary
    from packages.python.cue_library.constants import DEFAULT_REF_DIR
    from packages.python.cue_library.io import stereo_to_pcm


def ensure_refs(ref_dir: str | Path | None = None):
    lib = CueLibrary(peak_db=0.0)
    target_dir = Path(ref_dir) if ref_dir else Path(DEFAULT_REF_DIR)
    refs = lib.ensure_primary_references(target_dir=target_dir)
    start_stereo = lib.to_stereo(lib.start_cue())
    end_stereo = lib.to_stereo(lib.end_cue())
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

__all__ = ["ensure_refs"]
