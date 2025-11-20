from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from .sync_models import SyncRecording, CueAnchor, AudioCueInfo, GridSlot

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# JSON Loader
# ---------------------------------------------------------------------------

def _load_json(path: Path) -> Dict[str, Any]:
    """
    Load a JSON file or raise FileNotFoundError.
    """
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_media_entry(media_list: List[Dict[str, Any]], file_path: Path) -> Optional[Dict[str, Any]]:
    target = str(file_path)
    for m in media_list:
        if m.get("file") == target:
            return m
    return None


# ---------------------------------------------------------------------------
# Recording selection
# ---------------------------------------------------------------------------

def _select_recording(recordings_payload: Dict[str, Any], project_name: str) -> SyncRecording:
    """
    Select which recording metadata to use from recordings.json.
    Heuristic: latest created_at entry for the project.
    """
    recs = recordings_payload.get("recordings", [])
    candidates = [r for r in recs if r.get("project_name") == project_name]

    if not candidates:
        raise ValueError(f"No recording metadata for project '{project_name}'")

    # Use latest by created_at
    candidates.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    r = candidates[0]

    return SyncRecording(
        project_name=project_name,
        bpm=float(r["bpm_at_start"]),
        ts_num=int(r["ts_num"]),
        ts_den=int(r["ts_den"]),
        start_bar=float(r["start_recording_bar"]),
        end_bar=float(r["end_recording_bar"]),
        loop_start_bar=float(r["loop_start_bar"]),
        loop_end_bar=float(r["loop_end_bar"]),
    )


# ---------------------------------------------------------------------------
# Bar grid
# ---------------------------------------------------------------------------

def _bar_duration_s(rec: SyncRecording) -> float:
    """
    Duration of one bar for this project based on BPM and time signature.
    """
    beat_s = 60.0 / rec.bpm * (4.0 / rec.ts_den)
    return beat_s * rec.ts_num


def _build_bar_grid(
    rec: SyncRecording,
    *,
    audio_duration_s: float,
    bars_per_cut: int,
    cut_length_override_s: Optional[float] = None,
) -> List[GridSlot]:
    """
    Build a beat-aligned time grid across the audio duration.
    """
    bar_len = _bar_duration_s(rec)

    if cut_length_override_s is not None:
        cut_len = float(cut_length_override_s)
    else:
        cut_len = bar_len * max(1, bars_per_cut)

    slots: List[GridSlot] = []
    t = 0.0
    idx = 0
    while t + 1e-3 < audio_duration_s:
        slots.append(
            GridSlot(
                index=idx + 1,
                time_global=t,
                duration=min(cut_len, audio_duration_s - t),
                bar_index=idx * bars_per_cut,
            )
        )
        idx += 1
        t += cut_len

    log.info(
        "Built bar grid: %d slots (bar_len=%.3f, cut_len=%.3f, audio_dur=%.3f)",
        len(slots), bar_len, cut_len, audio_duration_s
    )
    return slots


# ---------------------------------------------------------------------------
# Audio cue parsing
# ---------------------------------------------------------------------------

def _parse_audio_cues(
    audio_path: Path,
    primary_matches: Dict[str, Any],
    postprocess_matches: Dict[str, Any],
) -> AudioCueInfo:
    """
    Extract cue anchor information for the audio export:
    - start cue (primary or secondary)
    - end cue (best-score stop_* or end*)
    """
    media_primary = primary_matches.get("media", [])
    media_post = postprocess_matches.get("media", [])

    primary_entry = _find_media_entry(media_primary, audio_path)
    post_entry = _find_media_entry(media_post, audio_path)

    if primary_entry is None or post_entry is None:
        raise ValueError(f"Audio file {audio_path} not found in cue match files")

    duration_s = float(post_entry.get("duration_s", 0.0))

    # Start anchor from the first pair
    pairs = primary_entry.get("pairs", [])
    if not pairs:
        raise ValueError(f"No cue pairs for audio file {audio_path}")
    sa = pairs[0].get("start_anchor")
    if not sa:
        raise ValueError(f"First cue pair has no start_anchor for audio file {audio_path}")

    start_anchor = CueAnchor(
        time_s=float(sa["time_s"]),
        ref_id=str(sa["ref_id"]),
    )

    # End cue heuristic
    end_hits = primary_entry.get("end_hits", []) or post_entry.get("end_hits", [])
    end_anchor: Optional[CueAnchor] = None

    if end_hits:
        # sort best score first
        end_hits_sorted = sorted(end_hits, key=lambda h: float(h.get("score", 0.0)), reverse=True)
        for eh in end_hits_sorted:
            ref = str(eh.get("ref_id", ""))
            if ref.startswith("stop_") or ref.startswith("end"):
                end_anchor = CueAnchor(
                    time_s=float(eh["time_s"]),
                    ref_id=ref,
                )
                break

    log.info(
        "Audio cue info: file=%s, duration=%.3fs, start=(%.3fs,%s), end=%s",
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
