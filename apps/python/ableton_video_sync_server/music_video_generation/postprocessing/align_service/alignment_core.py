from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class SegmentAlignment:
    seg_start: float
    seg_end: Optional[float]
    audio_cue: float
    relative_offset: float
    trim_start: float
    pad_start: float
    used_duration: float
    pad_end: float


def compute_segment_alignment(
    *,
    seg_start: float,
    seg_end: Optional[float],
    audio_cue: float,
    audio_duration: float,
    video_duration: float,
) -> SegmentAlignment:
    """
    Core alignment math used by BOTH:
      - FootageAlignService
      - multi_video_generator (sync_sequence)

    It mirrors the logic currently in FootageAlignService.align.
    """
    relative_offset = seg_start - audio_cue

    # where to start reading video
    trim_start = max(0.0, relative_offset)
    pad_start = max(0.0, -relative_offset)

    # segment duration
    if seg_end is not None:
        seg_duration = max(0.0, seg_end - seg_start)
    else:
        seg_duration = max(0.0, video_duration - seg_start)

    # available video after trimming
    available = min(seg_duration, max(0.0, video_duration - trim_start))

    # usable part of audio
    usable_audio = max(0.0, audio_duration - pad_start)
    used_duration = min(usable_audio, available)

    pad_end = max(0.0, audio_duration - pad_start - used_duration)

    return SegmentAlignment(
        seg_start=seg_start,
        seg_end=seg_end,
        audio_cue=audio_cue,
        relative_offset=relative_offset,
        trim_start=trim_start,
        pad_start=pad_start,
        used_duration=used_duration,
        pad_end=pad_end,
    )
