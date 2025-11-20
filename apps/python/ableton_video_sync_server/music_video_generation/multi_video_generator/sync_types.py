# apps/python/ableton_video_sync_server/music_video_generation/multi_video_generator/sync_types.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Core data models
# ---------------------------------------------------------------------------


@dataclass
class SyncRecording:
    project_name: str
    bpm: float
    ts_num: int
    ts_den: int
    start_bar: float
    end_bar: float
    loop_start_bar: float
    loop_end_bar: float


@dataclass
class CueAnchor:
    time_s: float
    ref_id: str


@dataclass
class CameraTake:
    file: Path
    window_start_s: float
    window_end_s: float
    start_anchor: CueAnchor
    end_anchor: Optional[CueAnchor]
    index: int  # 1-based index in JSON (primary_cue_matches)


@dataclass
class AudioCueInfo:
    file: Path
    duration_s: float
    start_anchor: CueAnchor
    end_hit: Optional[CueAnchor]


@dataclass
class ChosenCamera:
    """
    High-level choice: which camera file to use (we may still have multiple
    takes/windows for that file).
    """
    file: Path
    duration_s: float  # duration of the chosen reference window/file span


@dataclass
class GridSlot:
    """
    One bar-based cut slot on the *audio* timeline.
    """
    index: int
    time_global: float
    duration: float
    bar_index: int


@dataclass
class SimpleVideoRef:
    """
    Minimal adapter so CutClip can reference a 'video' with just a filename.
    """
    filename: str
