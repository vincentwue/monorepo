# apps/python/ableton_video_sync_server/music_video_generation/multi_video_generator/sync_grid.py
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .sync_types import GridSlot, SyncRecording

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Recording selection / tempo grid
# ---------------------------------------------------------------------------


def select_recording(recordings_payload: Dict[str, Any], project_name: str) -> SyncRecording:
    recs = recordings_payload.get("recordings", [])
    candidates = [r for r in recs if r.get("project_name") == project_name]

    if not candidates:
        raise ValueError(f"No recording metadata for project '{project_name}' in recordings.json")

    # Heuristic: latest created_at wins
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


def _bar_duration_s(rec: SyncRecording) -> float:
    """
    Duration of one bar in seconds, given BPM and time signature.
    Formula: bar = ts_num beats, each beat = 60/BPM * (4/ts_den) seconds.
    """
    beat_s = 60.0 / rec.bpm * (4.0 / rec.ts_den)
    return beat_s * rec.ts_num


def build_bar_grid(
    rec: SyncRecording,
    *,
    audio_duration_s: float,
    bars_per_cut: int,
    cut_length_override_s: Optional[float] = None,
) -> List[GridSlot]:
    """
    Build a list of GridSlot objects that cover the *audio* duration in
    fixed-size chunks based on bars_per_cut or a cut_length_override_s.
    """
    bar_len = _bar_duration_s(rec)
    if cut_length_override_s is not None:
        cut_len = float(cut_length_override_s)
    else:
        cut_len = bar_len * max(1, bars_per_cut)

    slots: List[GridSlot] = []
    t = 0.0
    idx = 0
    eps = 1e-3

    while t + eps < audio_duration_s:
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
        "Built bar grid: %d slots, bar_len=%.3fs, cut_len=%.3fs, audio_duration=%.3fs",
        len(slots),
        bar_len,
        cut_len,
        audio_duration_s,
    )
    return slots
