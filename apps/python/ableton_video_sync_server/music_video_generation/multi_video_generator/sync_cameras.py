from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .sync_models import CueAnchor, CameraTake

log = logging.getLogger(__name__)


def _index_segments_by_file(postprocess_matches: Dict[str, Any]) -> Dict[str, Dict[int, Dict[str, Any]]]:
    """
    Build a lookup: file -> (segment_index -> segment_dict).
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


def _parse_camera_takes(
    primary_matches: Dict[str, Any],
    postprocess_matches: Dict[str, Any],
) -> List[CameraTake]:
    """
    Parse camera takes from primary_cue_matches.json and postprocess_matches.json.

    Rules:
      - Only consider *video* media (no mp3/wav/etc. as video sources).
      - Each segment+pair combination becomes one CameraTake.
      - Windows come from postprocess_matches.segments[index], not from the pair
        window_* fields, so that we also get well-defined windows for segments
        whose status is 'missing_end'.
      - Track names from postprocess_matches (if present) are attached to each take
        so downstream selection can prioritize solos (e.g. bass-only).
    """
    media_primary = primary_matches.get("media", [])
    media_post = postprocess_matches.get("media", [])

    # Use postprocess.media_type to filter "real video".
    video_types = {"mp4", "mov", "mkv", "avi", "ts", "m4v"}
    post_by_file = {m["file"]: m for m in media_post if "file" in m}
    segments_by_file = _index_segments_by_file(postprocess_matches)

    takes: List[CameraTake] = []

    for entry in media_primary:
        file_str = entry.get("file")
        if not file_str:
            continue

        post = post_by_file.get(file_str)
        if not post:
            continue

        media_type = str(post.get("media_type", "")).lower()
        if media_type not in video_types:
            # Skip audio-like media (mp3, wav, etc.)
            continue

        file_path = Path(file_str)
        track_names = post.get("track_names") or []
        seg_map = segments_by_file.get(file_str, {})

        for pair in entry.get("pairs", []):
            idx = pair.get("index")
            if not isinstance(idx, int):
                continue

            segment = seg_map.get(idx)
            if not segment:
                log.debug("No segment found for file=%s pair_index=%s", file_str, idx)
                continue

            start = pair.get("start_anchor")
            if not start:
                # We need a start anchor to align to the audio; otherwise skip.
                continue

            # Window from segments, not from pair.
            window_start = float(segment["start_time_s"])
            window_end: Optional[float] = segment.get("end_time_s")

            # If the segment has no end_time_s (missing_end), fall back to the
            # media duration; if that is also missing, skip.
            if window_end is None:
                duration_s = post.get("duration_s")
                if duration_s is None:
                    log.debug(
                        "Skipping file=%s segment index=%d: no end_time_s and no duration_s.",
                        file_str,
                        idx,
                    )
                    continue
                # Leave a tiny safety margin at the end.
                window_end = max(window_start, float(duration_s) - 0.1)

            if window_end <= window_start:
                log.warning(
                    "Skipping camera segment with non-positive window (%s): start=%.3f, end=%.3f",
                    file_path,
                    window_start,
                    window_end,
                )
                continue

            end = pair.get("end_anchor")
            takes.append(
                CameraTake(
                    file=file_path,
                    window_start_s=window_start,
                    window_end_s=window_end,
                    start_anchor=CueAnchor(
                        time_s=float(start["time_s"]),
                        ref_id=str(start["ref_id"]),
                    ),
                    end_anchor=(
                        CueAnchor(
                            time_s=float(end["time_s"]),
                            ref_id=str(end["ref_id"]),
                        )
                        if end
                        else None
                    ),
                    index=int(idx),
                    track_names=list(track_names) if track_names else None,
                )
            )

    log.info("Parsed %d camera takes from primary_cue_matches/postprocess_matches", len(takes))
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
