from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


class ProjectDataNotFound(Exception):
    """Raised when recordings.json / postprocess_matches.json are missing or broken."""


@dataclass
class RecordingInfo:
    project_name: str
    file_path: str
    bpm_at_start: float
    ts_num: int
    ts_den: int
    start_sound_path: Optional[str]
    end_sound_path: Optional[str]
    start_recording_bar: Optional[float]
    end_recording_bar: Optional[float]
    duration_seconds: Optional[float]
    # you can extend this freely


@dataclass
class MediaInfo:
    file: str
    relative_path: str
    duration_s: float
    segments: List[Dict[str, Any]]
    cue_refs_used: List[str]
    start_hits: List[Dict[str, Any]]
    end_hits: List[Dict[str, Any]]
    media_type: str


class ProjectFiles:
    """
    Access helper around:

        <project_root>/recordings.json
        <project_root>/postprocess_matches.json

    Expects schemas like the examples you posted.
    """

    def __init__(self, project_root: str | Path):
        self.project_root = Path(project_root)
        self._recordings_raw: Optional[Dict[str, Any]] = None
        self._postproc_raw: Optional[Dict[str, Any]] = None

    # ------------------- low-level loaders -------------------

    def _recordings_path(self) -> Path:
        return self.project_root / "recordings.json"

    def _postprocess_path(self) -> Path:
        return self.project_root / "postprocess_matches.json"

    def _load_recordings_raw(self) -> Dict[str, Any]:
        if self._recordings_raw is not None:
            return self._recordings_raw
        path = self._recordings_path()
        if not path.exists():
            raise ProjectDataNotFound(f"recordings.json not found at {path}")
        try:
            self._recordings_raw = json.loads(path.read_text(encoding="utf-8"))
            return self._recordings_raw
        except Exception as exc:
            raise ProjectDataNotFound(f"Failed to read recordings.json at {path}: {exc}") from exc

    def _load_postproc_raw(self) -> Dict[str, Any]:
        if self._postproc_raw is not None:
            return self._postproc_raw
        path = self._postprocess_path()
        if not path.exists():
            raise ProjectDataNotFound(f"postprocess_matches.json not found at {path}")
        try:
            self._postproc_raw = json.loads(path.read_text(encoding="utf-8"))
            return self._postproc_raw
        except Exception as exc:
            raise ProjectDataNotFound(f"Failed to read postprocess_matches.json at {path}: {exc}") from exc

    # ------------------- recordings.json -------------------

    def list_recordings(self) -> List[RecordingInfo]:
        raw = self._load_recordings_raw()
        recs = []
        for item in raw.get("recordings", []):
            recs.append(
                RecordingInfo(
                    project_name=item.get("project_name", ""),
                    file_path=item.get("file_path", ""),
                    bpm_at_start=float(item.get("bpm_at_start", 120.0)),
                    ts_num=int(item.get("ts_num", 4)),
                    ts_den=int(item.get("ts_den", 4)),
                    start_sound_path=item.get("start_sound_path"),
                    end_sound_path=item.get("end_sound_path"),
                    start_recording_bar=item.get("start_recording_bar"),
                    end_recording_bar=item.get("end_recording_bar"),
                    duration_seconds=self._compute_duration_from_times(item),
                )
            )
        return recs

    def _compute_duration_from_times(self, item: Dict[str, Any]) -> Optional[float]:
        try:
            t0 = float(item.get("time_start_recording"))
            t1 = float(item.get("time_end_recording"))
            if t1 > t0:
                return t1 - t0
        except (TypeError, ValueError):
            pass
        return None

    def get_recording_by_project(self, project_name: str) -> RecordingInfo:
        for rec in self.list_recordings():
            if rec.project_name == project_name:
                return rec
        raise ProjectDataNotFound(f"No recording found for project_name={project_name!r} in recordings.json")

    def find_recording_by_cue(self, ref_id: str) -> Optional[RecordingInfo]:
        """
        Match a cue ref like 'start_20251119_214005_531.wav' against
        start_sound_path / end_sound_path basenames.
        """
        ref_id_lower = ref_id.lower()
        for rec in self.list_recordings():
            start = (rec.start_sound_path or "").lower()
            end = (rec.end_sound_path or "").lower()
            if ref_id_lower in start or ref_id_lower in end:
                return rec
        return None

    # ------------------- postprocess_matches.json -------------------

    def list_media(self) -> List[MediaInfo]:
        raw = self._load_postproc_raw()
        items = []
        for m in raw.get("media", []):
            items.append(
                MediaInfo(
                    file=m.get("file", ""),
                    relative_path=m.get("relative_path", ""),
                    duration_s=float(m.get("duration_s", 0.0) or 0.0),
                    segments=m.get("segments", []) or [],
                    cue_refs_used=m.get("cue_refs_used", []) or [],
                    start_hits=m.get("start_hits", []) or [],
                    end_hits=m.get("end_hits", []) or [],
                    media_type=m.get("media_type", ""),
                )
            )
        return items

    def find_media_by_cue(self, ref_id: str) -> List[MediaInfo]:
        """
        Return all media entries whose cue_refs_used contains ref_id (by basename).
        """
        ref_id_lower = ref_id.lower()
        result: List[MediaInfo] = []
        for m in self.list_media():
            if any(ref_id_lower in (c or "").lower() for c in m.cue_refs_used):
                result.append(m)
        return result

    def get_audio_media_for_project(self, project_name: str) -> Optional[MediaInfo]:
        """
        Best-effort choice of the main audio track for a project.
        For now: first media item whose file name starts with project_name and is an audio type.
        """
        name_lower = project_name.lower()
        candidates = []
        for m in self.list_media():
            base = Path(m.file).name.lower()
            if base.startswith(name_lower) and m.media_type.lower() in {"mp3", "wav", "m4a", "aac", "flac", "ogg"}:
                candidates.append(m)
        if candidates:
            return candidates[0]
        # fallback: first audio entry at all
        for m in self.list_media():
            if m.media_type.lower() in {"mp3", "wav", "m4a", "aac", "flac", "ogg"}:
                return m
        return None


# ------------------- helper factory -------------------

def get_project_root_from_any_path(path: Path) -> Path:
    """
    Given a path inside a project (audio/video/etc.), walk upwards until we find recordings.json.
    Assumes your layout is:

        <project_root>/
           recordings.json
           postprocess_matches.json
           footage/
           ableton/
           ...

    """
    path = path.resolve()
    for parent in [path] + list(path.parents):
        if (parent / "recordings.json").exists():
            return parent
    raise ProjectDataNotFound(f"Could not locate project root (recordings.json) for path {path}")


def make_store(project_root: Optional[str | Path] = None, hint_path: Optional[Path] = None) -> ProjectFiles:
    if project_root is not None:
        return ProjectFiles(project_root)
    if hint_path is not None:
        root = get_project_root_from_any_path(hint_path)
        return ProjectFiles(root)
    raise ValueError("Either project_root or hint_path must be provided.")
