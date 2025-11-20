from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .cut import CutClip
from .ffmpeg_render import FFmpegRenderer
from .sync_metadata import _load_json, _select_recording, _parse_audio_cues, _build_bar_grid
from .sync_cameras import _parse_camera_takes
from .sync_models import AudioCueInfo, CameraTake, GridSlot, SimpleVideoRef, SyncRecording
from ..project_files import make_store

log = logging.getLogger(__name__)


def _score_take_for_slot(
    slot: GridSlot,
    take: CameraTake,
    audio: AudioCueInfo,
) -> Optional[Dict[str, Any]]:
    """
    Try to map a timeline slot to a given camera take.

    Returns mapping information and a score if the slot can be placed within the
    take window; otherwise None.

    Heuristics:
      - Use cue anchors to align audio timeline to camera time.
      - Prefer takes where the clip lies comfortably inside the window (margin).
      - Prefer "solo" takes (few track_names) and especially bass-only tracks.
    """
    audio_start_t = audio.start_anchor.time_s
    video_start_t = take.start_anchor.time_s

    audio_t = slot.time_global

    # Raw mapping via cue alignment
    cam_t_raw = audio_t - audio_start_t + video_start_t

    window_start = take.window_start_s
    window_end = take.window_end_s

    ideal_start = cam_t_raw
    ideal_end = cam_t_raw + slot.duration

    mapping_kind = "ideal"

    if ideal_start < window_start or ideal_end > window_end:
        # Clamp into window where possible
        clamped_start = max(window_start, min(ideal_start, window_end - slot.duration))
        clamped_end = clamped_start + slot.duration
        if clamped_start < window_start or clamped_end > window_end:
            return None
        inpoint = clamped_start
        mapping_kind = "clamped"
    else:
        inpoint = ideal_start

    # The further we are from the edges of the take window, the better.
    margin_left = max(0.0, inpoint - window_start)
    margin_right = max(0.0, window_end - (inpoint + slot.duration))
    margin = min(margin_left, margin_right)

    # Track-based weighting: solos and bass get more weight.
    tracks = [t.lower() for t in (take.track_names or [])]
    track_bonus = 0.0
    if len(tracks) == 1:
        track_bonus += 0.6  # solo track (e.g. bass only)
    elif len(tracks) == 2:
        track_bonus += 0.3
    if "bass" in tracks:
        track_bonus += 0.4

    base = 1.0
    score = base + track_bonus + 0.001 * margin

    return {
        "inpoint": inpoint,
        "mapping_kind": mapping_kind,
        "score": score,
        "margin": margin,
        "tracks": tracks,
    }


def _build_sync_sequence(
    rec: SyncRecording,
    audio: AudioCueInfo,
    camera_takes: List[CameraTake],
    *,
    bars_per_cut: int,
    cut_length_override_s: Optional[float] = None,
    custom_duration_s: Optional[float] = None,
) -> Tuple[List[CutClip], Dict[str, Any]]:
    """
    Build a list of CutClip objects mapping audio beat-grid slots into a set of
    camera takes.

    Behaviour:
      - Never use audio as video (camera_takes already filtered to video only).
      - For each grid slot, evaluate all camera takes and pick the best scoring
        candidate based on:
          * cue alignment
          * staying inside the cue window
          * being a solo/feature take (e.g. bass-only)
      - If no camera can safely cover a slot, drop that slot.
    """
    if not camera_takes:
        raise ValueError("No camera takes available – cannot build sync edit without video.")

    audio_duration = custom_duration_s if custom_duration_s is not None else audio.duration_s

    slots = _build_bar_grid(
        rec,
        audio_duration_s=audio_duration,
        bars_per_cut=bars_per_cut,
        cut_length_override_s=cut_length_override_s,
    )

    seq: List[CutClip] = []
    plan_segments: List[Dict[str, Any]] = []

    for slot in slots:
        best_candidate: Optional[Dict[str, Any]] = None
        best_take: Optional[CameraTake] = None

        for take in camera_takes:
            cand = _score_take_for_slot(slot, take, audio)
            if cand is None:
                continue
            if best_candidate is None or cand["score"] > best_candidate["score"]:
                best_candidate = cand
                best_take = take

        if best_candidate is None or best_take is None:
            log.warning(
                "Slot %d at audio_t=%.3fs (dur=%.3fs) cannot be mapped into any camera window – dropping.",
                slot.index,
                slot.time_global,
                slot.duration,
            )
            continue

        inpoint = float(best_candidate["inpoint"])
        outpoint = inpoint + slot.duration
        mapping_kind = best_candidate["mapping_kind"]

        seq.append(
            CutClip(
                time_global=slot.time_global,
                duration=slot.duration,
                video=SimpleVideoRef(filename=str(best_take.file)),
                inpoint=inpoint,
                outpoint=outpoint,
            )
        )

        plan_segments.append(
            {
                "index": slot.index,
                "time_global": slot.time_global,
                "duration": slot.duration,
                "camera_file": str(best_take.file),
                "camera_take_index": best_take.index,
                "camera_track_names": best_take.track_names or [],
                "camera_inpoint": inpoint,
                "camera_outpoint": outpoint,
                "camera_mapping_kind": mapping_kind,
                "camera_score": best_candidate["score"],
                "camera_margin": best_candidate["margin"],
                "audio_time": slot.time_global,
                "audio_start_anchor": {
                    "time_s": audio.start_anchor.time_s,
                    "ref_id": audio.start_anchor.ref_id,
                },
            }
        )

    log.info("Built sync sequence: %d clips (from %d slots, %d camera takes)", len(seq), len(slots), len(camera_takes))

    # Debug payload summarising cameras and slots.
    cameras_debug = [
        {
            "file": str(t.file),
            "index": t.index,
            "window_start_s": t.window_start_s,
            "window_end_s": t.window_end_s,
            "start_anchor": {"time_s": t.start_anchor.time_s, "ref_id": t.start_anchor.ref_id},
            "end_anchor": (
                {"time_s": t.end_anchor.time_s, "ref_id": t.end_anchor.ref_id} if t.end_anchor else None
            ),
            "track_names": t.track_names or [],
        }
        for t in camera_takes
    ]

    debug_plan: Dict[str, Any] = {
        "kind": "sync_sequence_plan",
        "project_name": rec.project_name,
        "audio_file": str(audio.file),
        "audio_duration_s": audio_duration,
        "audio_start_anchor": {
            "time_s": audio.start_anchor.time_s,
            "ref_id": audio.start_anchor.ref_id,
        },
        "audio_end_hit": (
            {
                "time_s": audio.end_hit.time_s,
                "ref_id": audio.end_hit.ref_id,
            }
            if audio.end_hit
            else None
        ),
        "bars_per_cut": bars_per_cut,
        "cut_length_override_s": cut_length_override_s,
        "slots_total": len(slots),
        "clips_built": len(seq),
        "cameras": cameras_debug,
        "segments": plan_segments,
    }

    return seq, debug_plan


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
    only real camera video (no audio mp3 as visual source), and using all
    available camera takes (multi-camera aware).

    Returns the final video path.

    This keeps the existing contract used by pipeline.py:
        renderer.render_sequence(seq, str(out_file), str(audio_path))
    """
    if bars_per_cut is None:
        bars_per_cut = 1

    # Resolve project root via ProjectFiles/make_store
    store = make_store(project_root, hint_path=audio_path)
    root = store.project_root

    recordings_path = root / "recordings.json"
    postprocess_path = root / "postprocess_matches.json"
    primary_matches_path = root / "primary_cue_matches.json"

    log.info(
        "render_sync_edit: project=%s, audio=%s, project_root=%s",
        project_name,
        audio_path,
        root,
    )
    log.info(
        "render_sync_edit: loading metadata: recordings=%s, postprocess=%s, primary_cues=%s",
        recordings_path,
        postprocess_path,
        primary_matches_path,
    )

    recordings_payload = _load_json(recordings_path)
    postprocess_matches = _load_json(postprocess_path)
    primary_matches = _load_json(primary_matches_path)

    rec = _select_recording(recordings_payload, project_name=project_name)
    audio_info = _parse_audio_cues(audio_path, primary_matches, postprocess_matches)
    camera_takes = _parse_camera_takes(primary_matches, postprocess_matches)

    if not camera_takes:
        raise ValueError("No usable camera takes found – check cue detection results and media types.")

    seq, debug_plan = _build_sync_sequence(
        rec,
        audio_info,
        camera_takes,
        bars_per_cut=bars_per_cut,
        cut_length_override_s=cut_length_s_override,
        custom_duration_s=custom_duration_s,
    )

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
    renderer.render_sequence(seq, str(out_file), str(audio_path))

    return out_file
