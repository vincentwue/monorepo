from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from .cut import CutClip
from .sync_models import (
    AudioCueInfo,
    CameraTake,
    GridSlot,
    SimpleVideoRef,
    SyncRecording,
)
from .sync_metadata import _build_bar_grid, _bar_duration_s


log = logging.getLogger(__name__)


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
    Build a list of CutClip objects mapping audio beat-grid slots into multiple
    camera takes.

    Rules:
      - Never use audio as video (we already filtered to video-only in _parse_camera_takes).
      - All camera files / takes are candidates.
      - For each bar-grid slot:
          * Map the audio time into each camera using cue alignment.
          * Consider a take only where the corresponding part of the song is
            actually covered by that window (no infinite reuse).
          * Give *shorter* windows more weight (solo clips) so they win when
            they overlap.
    """
    if not camera_takes:
        raise ValueError("No camera takes found - cannot build sync edit without video")

    # What portion of the audio do we render?
    audio_duration = custom_duration_s if custom_duration_s is not None else audio.duration_s

    # Duration of one bar (seconds)
    bar_len = _bar_duration_s(rec)

    # Where does the *loop start bar* land in the audio export?
    # Assumption: audio.start_anchor.time_s corresponds to rec.start_bar.
    # Then bar b occurs at:
    #   t_audio(b) = audio_start_t + (b - rec.start_bar) * bar_len
    audio_start_t = audio.start_anchor.time_s
    audio_loop_start_t = audio_start_t + (rec.loop_start_bar - rec.start_bar) * bar_len

    if audio_loop_start_t >= audio_duration:
        raise ValueError(
            f"Grid origin {audio_loop_start_t:.3f}s is beyond audio duration "
            f"{audio_duration:.3f}s - check start_bar/loop_start_bar/anchors"
        )

    # We only build a grid from loop_start to the end of the audio
    grid_duration = audio_duration - audio_loop_start_t


    # Build global bar grid over the audio
    # Build bar grid *relative to loop_start* (t=0 corresponds to loop_start)
    slots: List[GridSlot] = _build_bar_grid(
        rec,
        audio_duration_s=grid_duration,
        bars_per_cut=bars_per_cut,
        cut_length_override_s=cut_length_override_s,
    )

    # -----------------------------------------------------------------------
    # Precompute per-take metadata: duration, solo weight, audio coverage
    # -----------------------------------------------------------------------
    take_infos: List[Dict[str, Any]] = []
    for t in camera_takes:
        take_dur = t.window_end_s - t.window_start_s
        if take_dur <= 0:
            continue

        # Audio coverage: the part of the song that this take actually covers
        # if we align cue-start to cue-start.
        audio_cov_start = audio_start_t
        audio_cov_end = min(audio_start_t + take_dur, audio_duration)
        if audio_cov_end <= audio_cov_start:
            log.warning(
                "Camera take idx=%d file=%s has no positive audio coverage; "
                "take_dur=%.3fs, audio_dur=%.3fs",
                t.index,
                t.file,
                take_dur,
                audio_duration,
            )
            continue

        # Solo weighting: shorter windows get *more* weight.
        # Example: if song is 25s and the take is only 8s, weight ~ 3.1
        solo_weight = audio_duration / take_dur
        # Avoid insane weights
        solo_weight = max(1.0, min(solo_weight, 6.0))

        take_infos.append(
            {
                "take": t,
                "duration_s": take_dur,
                "audio_cov_start": audio_cov_start,
                "audio_cov_end": audio_cov_end,
                "solo_weight": solo_weight,
            }
        )

    if not take_infos:
        raise ValueError("No usable camera takes after coverage analysis")

    log.info("Camera coverage / weights:")
    for info in take_infos:
        t: CameraTake = info["take"]
        log.info(
            "  file=%s idx=%d take_dur=%.3fs, audio_cov=[%.3f, %.3f], solo_weight=%.2f",
            t.file,
            t.index,
            info["duration_s"],
            info["audio_cov_start"],
            info["audio_cov_end"],
            info["solo_weight"],
        )

    seq: List[CutClip] = []
    plan_segments: List[Dict[str, Any]] = []
    last_take_index: Optional[int] = None

    # -----------------------------------------------------------------------
    # Slot-by-slot assignment
    # -----------------------------------------------------------------------
    for slot in slots:
        audio_t = audio_loop_start_t + slot.time_global
        slot_end = audio_t + slot.duration

        candidates: List[Tuple[float, float, str, Dict[str, Any]]] = []

        for info in take_infos:
            t: CameraTake = info["take"]
            cov_start = info["audio_cov_start"]
            cov_end = info["audio_cov_end"]

            # Does this slot fall inside the audio coverage of this take?
            if slot_end <= cov_start or audio_t >= cov_end:
                continue  # no overlap

            # Map audio time into camera time using cue alignment
            # (cue-start to cue-start)
            ideal_start = audio_t - audio_start_t + t.start_anchor.time_s
            ideal_end = ideal_start + slot.duration

            window_start = t.window_start_s
            window_end = t.window_end_s

            if ideal_start >= window_start and ideal_end <= window_end:
                # Perfectly inside the take window
                inpoint = ideal_start
                mapping_kind = "ideal"
                boundary_penalty = 0.0
            else:
                # Try to clamp to the take window, but do NOT treat this as
                # unlimited reuse - if we cannot fit the full slot, skip.
                clamped_start = max(window_start, min(ideal_start, window_end - slot.duration))
                clamped_end = clamped_start + slot.duration
                if clamped_start < window_start or clamped_end > window_end:
                    continue

                inpoint = clamped_start
                mapping_kind = "clamped"
                boundary_penalty = 0.3

            # Scoring:
            #  - solo_weight: shorter windows get higher score (solos)
            #  - small bias for "ideal" vs "clamped"
            solo_weight = info["solo_weight"]
            score = solo_weight - boundary_penalty

            candidates.append((score, inpoint, mapping_kind, info))

        if not candidates:
            log.warning(
                "No camera covers slot %d at audio_t=%.3fs (dur=%.3fs) - using BLACK filler.",
                slot.index,
                audio_t,
                slot.duration,
            )

            # Black filler clip for this bar
            black_ref = SimpleVideoRef(
                filename="__BLACK__",  # dummy path; renderer will special-case
                kind="black",
            )

            seq.append(
                CutClip(
                    time_global=slot.time_global,
                    duration=slot.duration,
                    video=black_ref,
                    inpoint=0.0,
                    outpoint=slot.duration,
                )
            )

            plan_segments.append(
                {
                    "slot_index": slot.index,
                    "time_global": audio_t,
                    "duration": slot.duration,
                    "bar_index": rec.loop_start_bar + slot.bar_index,
                    "camera_file": None,
                    "camera_take_index": None,
                    "camera_inpoint": None,
                    "camera_mapping_kind": "black",
                    "score": None,
                    "audio_time": audio_t,
                    "audio_start_anchor": {
                        "time_s": audio.start_anchor.time_s,
                        "ref_id": audio.start_anchor.ref_id,
                    },
                    "camera_start_anchor": None,
                    "camera_window_start_s": None,
                    "camera_window_end_s": None,
                    "audio_coverage_start_s": None,
                    "audio_coverage_end_s": None,
                }
            )
            last_take_index = None
            continue


        # Pick best candidate for this slot (optionally alternate takes when bars_per_cut == 1).
        candidates.sort(key=lambda x: x[0], reverse=True)
        chosen_score, inpoint, mapping_kind, info = candidates[0]
        if bars_per_cut == 1 and len(candidates) > 1 and last_take_index is not None:
            for cand in candidates:
                cand_take_idx = cand[3]["take"].index
                if cand_take_idx != last_take_index:
                    chosen_score, inpoint, mapping_kind, info = cand
                    break
        best_score = chosen_score
        t: CameraTake = info["take"]
        last_take_index = t.index

        seq.append(
            CutClip(
                time_global=slot.time_global,
                duration=slot.duration,
                video=SimpleVideoRef(filename=str(t.file)),
                inpoint=inpoint,
                outpoint=inpoint + slot.duration,
            )
        )

        plan_segments.append(
            {
                "slot_index": slot.index,
                "time_global": audio_t,  # real audio time
                "duration": slot.duration,
                "bar_index": rec.loop_start_bar + slot.bar_index,
                "camera_file": str(t.file),
                "camera_take_index": t.index,
                "camera_inpoint": inpoint,
                "camera_mapping_kind": mapping_kind,
                "score": best_score,
                "audio_time": audio_t,
                "audio_start_anchor": {
                    "time_s": audio.start_anchor.time_s,
                    "ref_id": audio.start_anchor.ref_id,
                },
                "camera_start_anchor": {
                    "time_s": t.start_anchor.time_s,
                    "ref_id": t.start_anchor.ref_id,
                },
                "camera_window_start_s": t.window_start_s,
                "camera_window_end_s": t.window_end_s,
                "audio_coverage_start_s": info["audio_cov_start"],
                "audio_coverage_end_s": info["audio_cov_end"],
            }
        )

    log.info("Built sync sequence: %d clips (from %d grid slots)", len(seq), len(slots))

    debug_plan: Dict[str, Any] = {
        "kind": "sync_sequence_plan",
        "project_name": rec.project_name,
        "audio_file": str(audio.file),
        "audio_duration_s": audio_duration,
        "audio_start_anchor": {
            "time_s": audio.start_anchor.time_s,
            "ref_id": audio.start_anchor.ref_id,
        },
        "audio_loop_start_s": audio_loop_start_t,
        "loop_start_bar": rec.loop_start_bar,
        "start_bar": rec.start_bar,

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
        "cameras": [
            {
                "file": str(info["take"].file),
                "take_index": info["take"].index,
                "window_start_s": info["take"].window_start_s,
                "window_end_s": info["take"].window_end_s,
                "start_anchor": {
                    "time_s": info["take"].start_anchor.time_s,
                    "ref_id": info["take"].start_anchor.ref_id,
                },
                "end_anchor": {
                    "time_s": info["take"].end_anchor.time_s,
                    "ref_id": info["take"].end_anchor.ref_id,
                }
                if info["take"].end_anchor
                else None,
                "duration_s": info["duration_s"],
                "audio_coverage": {
                    "start_s": info["audio_cov_start"],
                    "end_s": info["audio_cov_end"],
                },
                "solo_weight": info["solo_weight"],
            }
            for info in take_infos
        ],
        "segments": plan_segments,
    }

    return seq, debug_plan
