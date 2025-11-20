# apps/python/ableton_video_sync_server/music_video_generation/multi_video_generator/sync_cues.py
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .sync_types import AudioCueInfo, CameraTake, CueAnchor

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _find_media_entry(media_list: List[Dict[str, Any]], file_path: Path) -> Optional[Dict[str, Any]]:
    target = str(file_path)
    for m in media_list:
        if m.get("file") == target:
            return m
    return None


# ---------------------------------------------------------------------------
# Cue metadata parsing
# ---------------------------------------------------------------------------


def parse_audio_cues(
    audio_path: Path,
    primary_matches: Dict[str, Any],
    postprocess_matches: Dict[str, Any],
) -> AudioCueInfo:
    """
    Parse cue information for the master audio file from
    primary_cue_matches.json and postprocess_matches.json.
    """
    media_primary = primary_matches.get("media", [])
    media_post = postprocess_matches.get("media", [])

    primary_entry = _find_media_entry(media_primary, audio_path)
    post_entry = _find_media_entry(media_post, audio_path)

    if primary_entry is None or post_entry is None:
        raise ValueError(
            f"Audio file {audio_path} not found in primary_cue_matches.json/postprocess_matches.json"
        )

    duration_s = float(post_entry.get("duration_s", 0.0))

    # Primary start anchor
    pairs = primary_entry.get("pairs", [])
    if not pairs:
        raise ValueError(f"No cue pairs for audio file {audio_path} in primary_cue_matches.json")

    first_pair = pairs[0]
    sa = first_pair.get("start_anchor")
    if not sa:
        raise ValueError(f"First cue pair for audio file {audio_path} has no start_anchor")

    start_anchor = CueAnchor(time_s=float(sa["time_s"]), ref_id=str(sa["ref_id"]))

    # Try to infer an end hit (even though in your sample audio has missing_end)
    end_hits = primary_entry.get("end_hits", []) or post_entry.get("end_hits", [])
    end_anchor: Optional[CueAnchor] = None
    if end_hits:
        # Pick highest-score hit that looks like a stop cue (heuristic)
        end_hits_sorted = sorted(end_hits, key=lambda h: float(h.get("score", 0.0)), reverse=True)
        for eh in end_hits_sorted:
            ref = str(eh.get("ref_id", ""))
            if ref.startswith("stop_") or ref.startswith("end"):
                end_anchor = CueAnchor(time_s=float(eh["time_s"]), ref_id=ref)
                break

    log.info(
        "Audio cue info: file=%s, duration=%.3fs, start=(%.3fs, %s), end=%s",
        audio_path,
        duration_s,
        start_anchor.time_s,
        start_anchor.ref_id,
        f"(t={end_anchor.time_s:.3f}, ref={end_anchor.ref_id})" if end_anchor else "None",
    )

    return AudioCueInfo(
        file=audio_path,
        duration_s=duration_s,
        start_anchor=start_anchor,
        end_hit=end_anchor,
    )


def parse_camera_takes(
    primary_matches: Dict[str, Any],
    postprocess_matches: Dict[str, Any],
) -> List[CameraTake]:
    """
    Parse all complete cue windows for real video files (mp4/ts/etc.) from
    primary_cue_matches.json + postprocess_matches.json.
    """
    media_primary = primary_matches.get("media", [])
    media_post = postprocess_matches.get("media", [])

    # Use postprocess media_type to filter "real video" (no mp3/audio)
    video_types = {"mp4", "mov", "mkv", "avi", "ts", "m4v"}
    post_by_file = {m["file"]: m for m in media_post}

    takes: List[CameraTake] = []

    for entry in media_primary:
        file_str = entry.get("file")
        if not file_str:
            continue

        post = post_by_file.get(file_str)
        if not post:
            continue

        media_type = post.get("media_type", "").lower()
        if media_type not in video_types:
            # Skip audio-like media (mp3, wav, etc.)
            continue

        file_path = Path(file_str)
        for pair in entry.get("pairs", []):
            status = pair.get("status")
            if status != "complete":
                continue

            start = pair.get("start_anchor")
            end = pair.get("end_anchor")
            if not start or not end:
                continue

            window_start = float(pair.get("window_start_s", start["time_s"]))
            window_end = float(pair.get("window_end_s", end["time_s"]))

            takes.append(
                CameraTake(
                    file=file_path,
                    window_start_s=window_start,
                    window_end_s=window_end,
                    start_anchor=CueAnchor(
                        time_s=float(start["time_s"]),
                        ref_id=str(start["ref_id"]),
                    ),
                    end_anchor=CueAnchor(
                        time_s=float(end["time_s"]),
                        ref_id=str(end["ref_id"]),
                    ),
                    index=int(pair.get("index", 0)),
                )
            )

    log.info("Parsed %d camera takes from primary_cue_matches/postprocess_matches", len(takes))
    for t in takes:
        log.info(
            "  Take idx=%d file=%s window=[%.3f, %.3f] start=(%.3f,%s) end=(%.3f,%s)",
            t.index,
            t.file,
            t.window_start_s,
            t.window_end_s,
            t.start_anchor.time_s,
            t.start_anchor.ref_id,
            t.end_anchor.time_s if t.end_anchor else -1.0,
            t.end_anchor.ref_id if t.end_anchor else "None",
        )
    return takes
