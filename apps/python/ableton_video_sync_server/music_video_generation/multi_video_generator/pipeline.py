#!/usr/bin/env python3
"""
High-level orchestration helpers for the music video generation pipeline.

All metadata comes from:
- recordings.json
- postprocess_matches.json

No MongoDB / pymongo involved anymore.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from apps.python.ableton_video_sync_server.music_video_generation.multi_video_generator.sync_renderer import render_sync_video

from ..postprocessing import config as post_cfg  # if you still want default dirs
from ..postprocessing.audio_utils import has_ffmpeg

try:
    from cue_detection import gather_reference_library
except ImportError:  # pragma: no cover
    from packages.python.cue_detection import gather_reference_library

from ..postprocessing.main import iter_media, process_one  # optional if you still want to recompute
from .auto_bar_cuts import render_auto_bar_video
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


def _resolve_project_root(
    project_root: Optional[str | Path],
    audio_path: Path,
    out_file: Path,
) -> Path:
    """
    Best-effort way to decide the canonical project root.

    Priority:
      1) Explicit project_root argument (server path)
      2) Heuristic from audio path: .../<project>/footage/music/<file>
      3) Fallback: parent of the output directory
    """
    if project_root is not None:
        root = Path(project_root).expanduser().resolve()
        log.info("render_sync_edit: using explicit project_root=%s", root)
        return root

    # Heuristic from audio path
    audio_path = audio_path.expanduser().resolve()
    parts = list(audio_path.parts)
    # We expect .../<project>/footage/music/<file>
    try:
        idx_music = len(parts) - 2  # index of "music" if path ends with /music/<file>
        if idx_music >= 0 and parts[idx_music].lower() == "music":
            if idx_music - 1 >= 0 and parts[idx_music - 1].lower() == "footage":
                # project root is the parent of "footage"
                project_root_path = Path(*parts[: idx_music - 1])
                log.info(
                    "render_sync_edit: derived project_root=%s from audio_path=%s",
                    project_root_path,
                    audio_path,
                )
                return project_root_path
    except Exception:
        # fall through to fallback
        pass

    # Fallback: parent of the output dir
    root = out_file.parent.parent
    log.warning(
        "render_sync_edit: falling back to derived project_root=%s from output path=%s",
        root,
        out_file,
    )
    return root


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
    """
    Render a tempo-synced multi-camera edit.

    Behaviour:
      - Call render_sync_video(...) which currently writes into the legacy builds path.
      - Move the final video into <project_root>/generated/video_generation/.
      - Move the *_plan.json into <project_root>/.
      - Write *_video_gen.json into <project_root>/.
      - Return a metadata dict with the *final* canonical paths.
    """
    audio = Path(audio_path)
    _ensure_exists(audio, "audio track")

    # 1) Let the existing implementation render wherever it wants
    raw_out_file = render_sync_video(
        project_name,
        audio,
        bars_per_cut=bars_per_cut,
        cut_length_s_override=cut_length_s,
        custom_duration_s=custom_duration_s,
        debug=debug,
        project_root=project_root,
    )

    raw_out_path = Path(raw_out_file).expanduser().resolve()
    if not raw_out_path.exists():
        raise FileNotFoundError(f"render_sync_video did not produce output file: {raw_out_path}")

    # 2) Decide canonical project root
    project_root_path = _resolve_project_root(project_root, audio, raw_out_path)

    # 3) Final video location under project root
    final_video_dir = project_root_path / "generated" / "video_generation"
    final_video_dir.mkdir(parents=True, exist_ok=True)

    final_out_path = final_video_dir / raw_out_path.name
    if raw_out_path != final_out_path:
        log.info("render_sync_edit: moving video %s -> %s", raw_out_path, final_out_path)
        final_out_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(raw_out_path), str(final_out_path))

    # 4) Plan JSON: move from legacy location to project root
    raw_base, _ = os.path.splitext(str(raw_out_path))
    raw_plan_path = Path(f"{raw_base}_plan.json")

    final_plan_path: Optional[Path] = None
    if raw_plan_path.exists():
        final_plan_path = project_root_path / f"{final_out_path.stem}_plan.json"
        try:
            log.info("render_sync_edit: moving plan JSON %s -> %s", raw_plan_path, final_plan_path)
            shutil.move(str(raw_plan_path), str(final_plan_path))
        except Exception as exc:
            log.warning("render_sync_edit: failed to move plan JSON (%s)", exc)
            final_plan_path = raw_plan_path  # keep original location as a fallback
    else:
        log.warning("render_sync_edit: expected plan JSON not found at %s", raw_plan_path)

    # 5) video_gen JSON: always in project root
    final_video_gen_path = project_root_path / f"{final_out_path.stem}_video_gen.json"

    meta: Dict[str, Any] = {
        "kind": "sync_edit",
        "project_name": project_name,
        "project_root": str(project_root_path),
        "audio_path": str(audio),
        "output_file": str(final_out_path),
        "bars_per_cut": bars_per_cut,
        "cut_length_s": cut_length_s,
        "custom_duration_s": custom_duration_s,
        "debug": debug,
        # Debug/inspection artefacts
        "ffmpeg_plan_path": str(final_plan_path) if final_plan_path is not None else None,
        "video_gen_path": str(final_video_gen_path),
    }

    # 6) Optionally embed a lightweight summary of the ffmpeg plan
    if final_plan_path is not None and final_plan_path.exists():
        try:
            with open(final_plan_path, "r", encoding="utf-8") as f:
                plan_data = json.load(f)

            meta["ffmpeg_plan_summary"] = {
                "total_clips": plan_data.get("total_clips"),
                "total_video_duration": plan_data.get("total_video_duration"),
                "audio_source": plan_data.get("audio_source"),
                "width": plan_data.get("width"),
                "height": plan_data.get("height"),
                "fps": plan_data.get("fps"),
                "preset": plan_data.get("preset"),
                "use_nvenc": plan_data.get("use_nvenc"),
            }
        except Exception as exc:
            log.warning("render_sync_edit: failed to read/parse ffmpeg plan JSON (%s)", exc)

    # 7) Persist video_gen.json
    try:
        with open(final_video_gen_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)
        log.info("render_sync_edit: wrote video_gen metadata to %s", final_video_gen_path)
    except Exception as exc:
        log.warning("render_sync_edit: failed to write video_gen.json (%s)", exc)

    return meta


def render_auto_bar_edit(
    project_name: str,
    video_dir: str | Path,
    audio_path: str | Path,
    *,
    bars_per_cut: Optional[int] = None,
    custom_duration_s: Optional[float] = None,
    project_root: Optional[str | Path] = None,
) -> Dict[str, Any]:
    """
    Auto-bar edit currently keeps its legacy output location.

    We can later align this with the same project-root layout if desired
    (generated/video_generation + project-root JSONs).
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
