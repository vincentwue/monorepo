from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .sync_models import CueAnchor, CameraTake

log = logging.getLogger(__name__)


def _index_segments_by_file(postprocess_matches: Dict[str, Any]) -> Dict[str, Dict[int, Dict[str, Any]]]:
    """
    Build a lookup: file -> (segment_index -> segment_dict).

    Kept for potential external uses; not required by _parse_camera_takes.
    """
    by_file: Dict[str, Dict[int, Dict[str, Any]]] = {}
    for media in postprocess_matches.get("media", []):
        file_str = media.get("file")
        if not file_str:
            continue
        seg_map: Dict[int, Dict[str, Any]] = {}
        for seg in media.get("segments", []):
            idx = seg.get("index")
            if isinstance(idx, int):
                seg_map[idx] = seg
        by_file[file_str] = seg_map
    return by_file


def _pick_best_hit_in_window(
    hits: List[Dict[str, Any]],
    window_start: float,
    window_end: float,
    *,

    prefer_stop_like: bool = False,
) -> Optional[Dict[str, Any]]:
    """
    Select the best hit for a given window [window_start, window_end].

    Strategy:
      1. Prefer hits whose time_s lies inside the window.
      2. If none are inside, pick the closest in time.
      3. If prefer_stop_like=True, we additionally prioritize ref_ids that
         look like stop/end cues (stop_*, end*).
      4. Among candidates, use score DESC, then |time_s - window_center| ASC.
    """
    if not hits:
        return None

    window_center = 0.5 * (window_start + window_end)

    def _score_key(h: Dict[str, Any]) -> tuple:
        t = float(h.get("time_s", 0.0))
        score = float(h.get("score", 0.0))
        ref = str(h.get("ref_id", ""))
        in_window = (window_start <= t <= window_end)
        is_stop_like = prefer_stop_like and (ref.startswith("stop_") or ref.startswith("end"))
        # We want:
        #   - in_window first (True > False),
        #   - then stop-like (True > False) if requested,
        #   - then score DESC,
        #   - then |time - center| ASC.
        return (
            0 if in_window else 1,                # in-window preferred
            0 if is_stop_like else 1,             # stop-like preferred
            -score,                               # higher score first
            abs(t - window_center),               # closer to center
        )

    hits_sorted = sorted(hits, key=_score_key)
    return hits_sorted[0] if hits_sorted else None


def _parse_camera_takes(
    postprocess_matches: Dict[str, Any],
) -> List[CameraTake]:
    """
    Parse camera takes from postprocess_matches.json ONLY.

    In the current JSON, start_hits/end_hits are MEDIA-level, and segments
    only carry time windows. This function maps the media-level hits onto
    each segment by picking the best hit for that segment window.

    IMPORTANT: The start_anchor.time_s is set to the *segment start* time,
    so that the multi-video generator uses the same notion of "cue position"
    as FootageAlignService (seg_start).
    """
    media_post = postprocess_matches.get("media", [])

    video_types = {"mp4", "mov", "mkv", "avi", "ts", "m4v"}
    takes: List[CameraTake] = []

    for post in media_post:
        file_str = post.get("file")
        if not file_str:
            continue

        media_type = str(post.get("media_type", "")).lower()
        if media_type not in video_types:
            # Skip audio-like media (mp3, wav, etc.)
            continue

        file_path = Path(file_str)
        track_names = post.get("track_names") or []
        duration_s = float(post.get("duration_s", 0.0)) if post.get("duration_s") is not None else None

        segments = post.get("segments", [])
        if not isinstance(segments, list):
            continue

        media_start_hits = post.get("start_hits", []) or []
        media_end_hits = post.get("end_hits", []) or []

        for segment in segments:
            idx = segment.get("index")
            if not isinstance(idx, int):
                continue

            window_start = float(segment.get("start_time_s", 0.0))
            window_end: Optional[float] = segment.get("end_time_s")

            # If the segment has no end_time_s, fall back to media duration.
            if window_end is None:
                if duration_s is None:
                    log.debug(
                        "Skipping file=%s segment index=%d: no end_time_s and no duration_s.",
                        file_str,
                        idx,
                    )
                    continue
                window_end = max(window_start, float(duration_s) - 0.1)

            window_end = float(window_end)
            if window_end <= window_start:
                log.warning(
                    "Skipping camera segment with non-positive window (%s): start=%.3f, end=%.3f",
                    file_path,
                    window_start,
                    window_end,
                )
                continue

            # --- Choose start hit for this segment ---
            best_start_hit = _pick_best_hit_in_window(media_start_hits, window_start, window_end)
            if best_start_hit is None:
                log.debug(
                    "Skipping file=%s segment index=%d: no suitable start hit in/near window [%.3f, %.3f].",
                    file_str,
                    idx,
                    window_start,
                    window_end,
                )
                continue

            # IMPORTANT:
            # - align_service uses seg_start as the cue position.
            # - we set time_s to window_start to mirror that behavior.
            start_anchor = CueAnchor(
                time_s=window_start,
                ref_id=str(best_start_hit.get("ref_id", "")),
            )

            # --- Choose end hit for this segment (optional) ---
            best_end_hit = _pick_best_hit_in_window(
                media_end_hits,
                window_start,
                window_end,
                prefer_stop_like=True,
            )
            end_anchor: Optional[CueAnchor] = None
            if best_end_hit is not None:
                end_anchor = CueAnchor(
                    time_s=float(best_end_hit["time_s"]),
                    ref_id=str(best_end_hit.get("ref_id", "")),
                )

            takes.append(
                CameraTake(
                    file=file_path,
                    window_start_s=window_start,
                    window_end_s=window_end,
                    start_anchor=start_anchor,
                    end_anchor=end_anchor,
                    index=int(idx),
                    track_names=list(track_names) if track_names else None,
                )
            )

    log.info("Parsed %d camera takes from postprocess_matches", len(takes))
    for t in takes:
        log.info(
            "  Take idx=%d file=%s window=[%.3f, %.3f] start=(%.3f,%s) end=%s tracks=%s",
            t.index,
            t.file,
            t.window_start_s,
            t.window_end_s,
            t.start_anchor.time_s,
            t.start_anchor.ref_id,
            (
                f"(%.3f,%s)" % (t.end_anchor.time_s, t.end_anchor.ref_id)
                if t.end_anchor
                else "None"
            ),
            ",".join(t.track_names or []),
        )
    return takes
