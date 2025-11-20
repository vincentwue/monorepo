#!/usr/bin/env python3
"""
High-level orchestration helpers for the music video generation pipeline.

All metadata comes from:
- recordings.json
- postprocess_matches.json

No MongoDB / pymongo involved anymore.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..postprocessing import config as post_cfg  # if you still want default dirs
from ..postprocessing.audio_utils import has_ffmpeg

try:
    from cue_detection import gather_reference_library
except ImportError:  # pragma: no cover
    from packages.python.cue_detection import gather_reference_library

from ..postprocessing.main import iter_media, process_one  # optional if you still want to recompute
from .auto_bar_cuts import render_auto_bar_video
from .sync_cuts_from_recordings import render_sync_video
from ..export_matcher import match_ableton_export_to_recording as _match_export_internal
from ..project_files import ProjectFiles, make_store

log = logging.getLogger(__name__)


def _ensure_path(value: Optional[str | Path], fallback: Path) -> Path:
    if value is None:
        return Path(fallback)
    return Path(value)


def _ensure_exists(path: Path, kind: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{kind} path not found: {path}")


def _serialize_segments(res: dict) -> Dict[str, Any]:
    return {
        "file": res.get("file"),
        "duration_s": res.get("duration_s"),
        "segments": res.get("segments", []),
        "cue_refs_used": res.get("cue_refs_used", []),
        "notes": res.get("notes", []),
    }


def run_postprocessing_from_json(
    *,
    project_root: str | Path,
) -> Dict[str, Any]:
    """
    Lightweight wrapper that just exposes the content of postprocess_matches.json
    in the same style as the previous 'run_postprocessing' summary.
    """
    store = ProjectFiles(project_root)
    media = store.list_media()

    items: List[Dict[str, Any]] = []
    for m in media:
        items.append(
            {
                "file": m.file,
                "status": "ok",
                "result": {
                    "file": m.file,
                    "duration_s": m.duration_s,
                    "segments": m.segments,
                    "cue_refs_used": m.cue_refs_used,
                    "notes": [],
                },
            }
        )

    pp_path = store._postprocess_path()
    return {
        "input_path": str(pp_path.parent),
        "ref_dir": str(post_cfg.REF_DIR),
        "total": len(items),
        "processed": len(items),
        "items": items,
    }


def match_export_to_recording(
    audio_path: str | Path,
    *,
    project_root: Optional[str | Path] = None,
) -> Dict[str, Any]:
    """
    Matches a rendered Ableton export to its recording using recordings.json.
    """
    path = Path(audio_path)
    _ensure_exists(path, "audio export")

    store = make_store(project_root, hint_path=path)
    match, cue_info = _match_export_internal(path, store)

    recording_payload: Dict[str, Any] | None = None
    project_name: Optional[str] = None
    if match:
        rec = match["recording"]
        project_name = match["project_name"]
        recording_payload = {
            "project_name": project_name,
            "start_sound_path": rec.start_sound_path,
            "end_sound_path": rec.end_sound_path,
        }

    return {
        "audio_path": str(path),
        "project_root": str(store.project_root),
        "matched": recording_payload is not None,
        "project_name": project_name,
        "recording": recording_payload,
        "cue": cue_info,
    }


def render_sync_edit(
    project_name: str,
    audio_path: str | Path,
    *,
    bars_per_cut: Optional[int] = None,
    cut_length_s: Optional[float] = None,
    custom_duration_s: Optional[float] = None,
    debug: Optional[bool] = None,
    project_root: Optional[str | Path] = None,
) -> Dict[str, Any]:
    audio = Path(audio_path)
    _ensure_exists(audio, "audio track")

    out_file = render_sync_video(
        project_name,
        audio,
        bars_per_cut=bars_per_cut,
        cut_length_s_override=cut_length_s,
        custom_duration_s=custom_duration_s,
        debug=debug,
        project_root=project_root,
    )

    return {
        "project_name": project_name,
        "audio_path": str(audio),
        "output_file": out_file,
        "bars_per_cut": bars_per_cut,
        "cut_length_s": cut_length_s,
        "custom_duration_s": custom_duration_s,
    }


def render_auto_bar_edit(
    project_name: str,
    video_dir: str | Path,
    audio_path: str | Path,
    *,
    bars_per_cut: Optional[int] = None,
    custom_duration_s: Optional[float] = None,
    project_root: Optional[str | Path] = None,
) -> Dict[str, Any]:
    videos_root = Path(video_dir)
    _ensure_exists(videos_root, "video directory")
    audio = Path(audio_path)
    _ensure_exists(audio, "audio track")

    out_file = render_auto_bar_video(
        project_name,
        videos_root,
        audio,
        bars_per_cut=bars_per_cut,
        custom_duration_s=custom_duration_s,
        project_root=project_root,
    )

    return {
        "project_name": project_name,
        "video_dir": str(videos_root),
        "audio_path": str(audio),
        "output_file": out_file,
        "bars_per_cut": bars_per_cut,
        "custom_duration_s": custom_duration_s,
    }


def run_full_pipeline(
    project_name: str,
    video_dir: str | Path,
    audio_path: str | Path,
    *,
    project_root: Optional[str | Path] = None,
    match_audio_path: Optional[str | Path] = None,
    bars_per_cut: Optional[int] = None,
    cut_length_s: Optional[float] = None,
    custom_duration_s: Optional[float] = None,
    skip_postprocess: bool = False,
    skip_match: bool = False,
    skip_sync: bool = False,
    skip_auto: bool = False,
) -> Dict[str, Any]:
    """
    Convenience wrapper executing the typical production pipeline, purely from JSON.
    """

    result: Dict[str, Any] = {
        "project_name": project_name,
        "video_dir": str(video_dir),
        "audio_path": str(audio_path),
    }

    if not skip_postprocess and project_root is not None:
        result["postprocess"] = run_postprocessing_from_json(project_root=project_root)

    if not skip_match:
        export_audio = match_audio_path or audio_path
        result["export_match"] = match_export_to_recording(
            export_audio,
            project_root=project_root,
        )

    if not skip_sync:
        result["sync_video"] = render_sync_edit(
            project_name,
            audio_path,
            bars_per_cut=bars_per_cut,
            cut_length_s=cut_length_s,
            custom_duration_s=custom_duration_s,
            debug=None,
            project_root=project_root,
        )

    if not skip_auto:
        result["auto_bar_video"] = render_auto_bar_edit(
            project_name,
            video_dir,
            audio_path,
            bars_per_cut=bars_per_cut,
            custom_duration_s=custom_duration_s,
            project_root=project_root,
        )

    return result
