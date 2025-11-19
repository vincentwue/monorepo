from .audio_output import AudioOutputSelector
from .player import CuePlayer, unique_cue, mk_barker_bpsk, to_stereo, FS
from .preview import RecordingCuePreviewer
from .output import CueOutputService, CueSpeakerSettings
from .generation import ensure_refs, ensure_stop_ref, mk_stop_unique
from .detection import gather_reference_library, compute_matches, build_segments
from .services import PrimaryCueDetectionService

__all__ = [
    "AudioOutputSelector",
    "CuePlayer",
    "unique_cue",
    "mk_barker_bpsk",
    "to_stereo",
    "FS",
    "CueOutputService",
    "CueSpeakerSettings",
    "RecordingCuePreviewer",
    "ensure_refs",
    "ensure_stop_ref",
    "mk_stop_unique",
    "gather_reference_library",
    "compute_matches",
    "build_segments",
    "PrimaryCueDetectionService",
]
