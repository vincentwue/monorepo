from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from ..project_files import make_store
from .ffmpeg_render import FFmpegRenderer
from .sync_cameras import _parse_camera_takes
from .sync_metadata import _load_json, _select_recording, _parse_audio_cues
from .sync_sequence import _build_sync_sequence

log = logging.getLogger(__name__)


def render_sync_video(
    project_name: str,
    audio_path: Path,
    *,
    bars_per_cut: Optional[int] = None,
    cut_length_s_override: Optional[float] = None,
    custom_duration_s: Optional[float] = None,
    debug: Optional[bool] = None,
    project_root: Optional[str | Path] = None,
) -> Path:
    """
    Build a tempo-locked sync edit for a given project + audio export using
    *all* real camera video (multi-camera, no audio-as-video).

    Returns the final video path.

    This keeps the contract used by pipeline.py:
        renderer.render_sequence(seq, str(out_file), str(audio_path))

    NOTE: This variant no longer relies on primary cue matches
    (primary_cue_matches.json). All cue / alignment information is expected
    to be obtainable from postprocess_matches.json and recordings.json.
    """
    if bars_per_cut is None:
        bars_per_cut = 1

    # Resolve project root via ProjectFiles/make_store
    store = make_store(project_root, hint_path=audio_path)
    root: Path = store.project_root

    recordings_path = root / "recordings.json"
    postprocess_path = root / "postprocess_matches.json"

    log.info(
        "render_sync_edit: project=%s, audio=%s, project_root=%s",
        project_name,
        audio_path,
        root,
    )
    log.info(
        "render_sync_edit: loading metadata: recordings=%s, postprocess=%s",
        recordings_path,
        postprocess_path,
    )

    recordings_payload: Dict[str, Any] = _load_json(recordings_path)
    postprocess_matches: Dict[str, Any] = _load_json(postprocess_path)

    # Select the relevant recording for this project
    rec = _select_recording(recordings_payload, project_name=project_name)

    # Parse audio alignment info and camera takes using ONLY postprocess_matches.
    # _parse_audio_cues/_parse_camera_takes are expected to be updated to work
    # without primary cue matches.
    audio_info = _parse_audio_cues(audio_path, postprocess_matches)
    camera_takes = _parse_camera_takes(postprocess_matches)

    seq, debug_plan = _build_sync_sequence(
        rec,
        audio_info,
        camera_takes,
        bars_per_cut=bars_per_cut,
        cut_length_override_s=cut_length_s_override,
        custom_duration_s=custom_duration_s,
    )

    audio_offset_s = float(debug_plan.get("audio_loop_start_s", 0.0))

    # Output path: inside project/generated/video_generation
    out_dir = root / "generated" / "video_generation"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{project_name}_sync_edit.mp4"

    # Save sync-level debug plan next to project root
    video_gen_path = root / f"{project_name}_sync_edit_video_gen.json"
    debug_plan_out = {
        **debug_plan,
        "output_file": str(out_file),
        "project_root": str(root),
    }
    with video_gen_path.open("w", encoding="utf-8") as f:
        json.dump(debug_plan_out, f, indent=2)
    log.info("Wrote sync edit plan JSON to %s", video_gen_path)

    # Render video with FFmpegRenderer; renderer itself will write the ffmpeg
    # segment plan JSON (underwater_sync_edit_plan.json) as before.
    renderer = FFmpegRenderer(debug=bool(debug))
    log.info(
        "Calling FFmpegRenderer.render_sequence with %d clips, output=%s, audio=%s",
        len(seq),
        out_file,
        audio_path,
    )
    renderer.render_sequence(
        seq,
        output_path=str(out_file),
        audio_source=str(audio_info.file),
        audio_offset_s=audio_offset_s,
    )
    return out_file
