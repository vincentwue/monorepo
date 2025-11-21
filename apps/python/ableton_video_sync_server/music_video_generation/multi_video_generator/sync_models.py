from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


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
    index: int  # 1-based index in JSON
    # Track names from postprocess_matches (e.g. ["bass"], ["voice","guitar"])
    track_names: Optional[List[str]] = None


@dataclass
class AudioCueInfo:
    file: Path
    duration_s: float
    start_anchor: CueAnchor
    end_hit: Optional[CueAnchor]


@dataclass
class GridSlot:
    index: int
    time_global: float
    duration: float
    bar_index: int


@dataclass
class SimpleVideoRef:
    filename: str
    camera_id: Optional[str] = None
    kind: str = "camera"  # "camera" or "black"