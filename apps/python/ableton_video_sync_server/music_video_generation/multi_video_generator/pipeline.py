#!/usr/bin/env python3
"""
High-level orchestration helpers for the music video generation pipeline.

These functions wrap individual steps (cue postprocessing, export matching,
sync-based edits, auto-bar edits) so they can be reused by the CLI and the API.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from pymongo import MongoClient

from ..postprocessing import config as post_cfg
from ..postprocessing.audio_utils import has_ffmpeg
from packages.python.ableton_cues.detection import gather_reference_library
from ..postprocessing.main import iter_media, process_one
from ..postprocessing.mongo_writer import insert_postprocessing_result
from .auto_bar_cuts import render_auto_bar_video
from .sync_cuts_from_recordings import render_sync_video
from ..export_matcher import match_ableton_export_to_recording

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


def run_postprocessing(
    *,
    input_path: Optional[str | Path] = None,
    ref_dir: Optional[str | Path] = None,
    mongo_uri: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Detects cues for all media inside `input_path` and writes the results to MongoDB.
    Returns a summary payload for UI consumption.
    """

    media_root = _ensure_path(input_path, post_cfg.INPUT_PATH)
    cue_root = _ensure_path(ref_dir, post_cfg.REF_DIR)
    uri = mongo_uri or post_cfg.MONGO_URI

    _ensure_exists(media_root, "input")
    _ensure_exists(cue_root, "cue reference")

    if not has_ffmpeg():
        raise RuntimeError("ffmpeg/ffprobe not found in PATH.")

    refs = gather_reference_library(cue_root)
    media_files = list(iter_media(media_root))
    if not media_files:
        raise RuntimeError(f"No media files found under {media_root}")

    items: List[Dict[str, Any]] = []
    client = MongoClient(uri)
    try:
        for path in media_files:
            entry: Dict[str, Any] = {"file": str(path)}
            try:
                res = process_one(path, refs)
                insert_postprocessing_result(client, res)
                entry.update({"status": "ok", "result": _serialize_segments(res)})
            except Exception as exc:  # pragma: no cover - defensive logging
                log.exception("Postprocessing failed for %s", path)
                entry.update({"status": "error", "error": str(exc)})
            items.append(entry)
    finally:
        client.close()

    return {
        "input_path": str(media_root),
        "ref_dir": str(cue_root),
        "mongo_uri": uri,
        "total": len(items),
        "processed": sum(1 for item in items if item.get("status") == "ok"),
        "items": items,
    }


def match_export_to_recording(
    audio_path: str | Path,
    *,
    mongo_uri: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Matches a rendered Ableton export to its recording document via cue detection.
    """

    path = Path(audio_path)
    _ensure_exists(path, "audio export")

    uri = mongo_uri or post_cfg.MONGO_URI
    client = MongoClient(uri)
    try:
        rec_doc, cue_info = match_ableton_export_to_recording(path, client)
    finally:
        client.close()

    recording_payload: Dict[str, Any] | None = None
    if rec_doc:
        fields = rec_doc.get("fields", {}).get("ableton_recording", {})
        recording_payload = {
            "id": str(rec_doc.get("_id")),
            "title": rec_doc.get("title"),
            "project_name": fields.get("project_name"),
            "start_sound_path": fields.get("start_sound_path"),
            "end_sound_path": fields.get("end_sound_path"),
        }

    return {
        "audio_path": str(path),
        "mongo_uri": uri,
        "matched": recording_payload is not None,
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
) -> Dict[str, Any]:
    """
    Builds a tempo-aligned edit using the cue segments already stored in MongoDB.
    """

    audio = Path(audio_path)
    _ensure_exists(audio, "audio track")

    out_file = render_sync_video(
        project_name,
        audio,
        bars_per_cut=bars_per_cut,
        cut_length_s_override=cut_length_s,
        custom_duration_s=custom_duration_s,
        debug=debug,
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
) -> Dict[str, Any]:
    """
    Generates an automatic bar-length cut using the available camera clips.
    """

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
    input_path: Optional[str | Path] = None,
    ref_dir: Optional[str | Path] = None,
    match_audio_path: Optional[str | Path] = None,
    bars_per_cut: Optional[int] = None,
    cut_length_s: Optional[float] = None,
    custom_duration_s: Optional[float] = None,
    mongo_uri: Optional[str] = None,
    skip_postprocess: bool = False,
    skip_match: bool = False,
    skip_sync: bool = False,
    skip_auto: bool = False,
) -> Dict[str, Any]:
    """
    Convenience wrapper that executes the typical production pipeline in order.
    """

    result: Dict[str, Any] = {
        "project_name": project_name,
        "video_dir": str(video_dir),
        "audio_path": str(audio_path),
    }

    if not skip_postprocess:
        result["postprocess"] = run_postprocessing(
            input_path=input_path,
            ref_dir=ref_dir,
            mongo_uri=mongo_uri,
        )

    if not skip_match:
        export_audio = match_audio_path or audio_path
        result["export_match"] = match_export_to_recording(
            export_audio,
            mongo_uri=mongo_uri,
        )

    if not skip_sync:
        result["sync_video"] = render_sync_edit(
            project_name,
            audio_path,
            bars_per_cut=bars_per_cut,
            cut_length_s=cut_length_s,
            custom_duration_s=custom_duration_s,
        )

    if not skip_auto:
        result["auto_bar_video"] = render_auto_bar_edit(
            project_name,
            video_dir,
            audio_path,
            bars_per_cut=bars_per_cut,
            custom_duration_s=custom_duration_s,
        )

    return result
