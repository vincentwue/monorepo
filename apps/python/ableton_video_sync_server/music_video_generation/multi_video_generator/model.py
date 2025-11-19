# playground/multi_video_generator/model.py

import os
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from .media import get_video_props


@dataclass
class Video:
    filename: str
    name: Optional[str] = None
    sync_time: Optional[float] = None
    duration: float = field(init=False, default=0.0)
    vcodec: Optional[str] = field(init=False, default=None)
    fps: Optional[float] = field(init=False, default=None)

    def __post_init__(self):
        self.name = self.name or os.path.splitext(os.path.basename(self.filename))[0]
        try:
            self.duration, self.vcodec, self.fps = get_video_props(self.filename)
        except Exception as e:
            print(f"[WARN] ffprobe failed for {self.filename}: {e}")

    @property
    def is_hevc(self) -> bool:
        return (self.vcodec or "").lower() in {"hevc", "h265"}


@dataclass
class VideoGroup:
    folder_path: str
    sync_map: Optional[Dict[str, float]] = None
    name: str = field(init=False)
    videos: List[Video] = field(default_factory=list)

    def __post_init__(self):
        self.name = os.path.basename(self.folder_path)
        self.load_videos()
        if self.sync_map:
            self.set_sync_times(self.sync_map)

    def load_videos(self):
        for f in sorted(os.listdir(self.folder_path)):
            if f.lower().endswith((".mp4", ".mov", ".mkv")) and "seg" in f:
                self.videos.append(Video(os.path.join(self.folder_path, f)))

    def set_sync_times(self, sync_map: Dict[str, float]):
        for v in self.videos:
            if v.name in sync_map:
                v.sync_time = float(sync_map[v.name])


@dataclass
class VideoProject:
    root_folder: str
    bpm: float
    cut_times: List[float]  # globale Zeiten (Sek.)
    groups: List[VideoGroup] = field(default_factory=list)

    def load_groups(self):
        """Jeder Ordner mit Videos wird als VideoGroup aufgenommen."""
        for root, _dirs, files in os.walk(self.root_folder):
            if any(f.lower().endswith((".mp4", ".mov", ".mkv")) for f in files):
                self.groups.append(VideoGroup(root))

    @property
    def beat_seconds(self) -> float:
        return 60.0 / self.bpm

    def ensure_sync_times_set(self):
        missing = []
        for g in self.groups:
            for v in g.videos:
                if v.sync_time is None:
                    missing.append(v.filename)
        if missing:
            print("[INFO] Videos ohne sync_time:")
            for m in missing:
                print("  -", m)
