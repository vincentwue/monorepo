from .detection import (
    build_segments,
    classify_reference_name,
    compute_matches,
    deduplicate_hits,
    find_all_matches,
    gather_reference_library,
)
from .audio import fade, read_wav_mono, xcorr_valid_spectrogram, DEFAULT_FS, DEFAULT_FADE_MS

__all__ = [
    "build_segments",
    "classify_reference_name",
    "compute_matches",
    "deduplicate_hits",
    "find_all_matches",
    "gather_reference_library",
    "fade",
    "read_wav_mono",
    "xcorr_valid",
    "DEFAULT_FS",
    "DEFAULT_FADE_MS",
]
