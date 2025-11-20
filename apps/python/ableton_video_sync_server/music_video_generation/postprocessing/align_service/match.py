from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Sequence

from loguru import logger


_TIME_TOL = 0.5  # seconds tolerance between segment start and cue hit


def _basename(path_str: str | None) -> Optional[str]:
    if not isinstance(path_str, str) or not path_str:
        return None
    return Path(path_str).name.lower()


def _find_nearest_hit(
    seg_start: float,
    hits: Sequence[Dict],
    tol: float,
) -> Optional[Dict]:
    best: Optional[Dict] = None
    best_dt = tol
    for hit in hits or []:
        t = hit.get("time_s")
        if not isinstance(t, (int, float)):
            continue
        dt = abs(float(t) - seg_start)
        if dt <= best_dt:
            best_dt = dt
            best = hit
    return best


def find_recording_for_segment(
    *,
    seg_start: float,
    seg_end: Optional[float],
    start_hits: Sequence[Dict],
    end_hits: Sequence[Dict],
    recordings: Sequence[Dict],
) -> Optional[Dict]:
    """
    Heuristic mapping:

    - Find the nearest start_hit to seg_start within _TIME_TOL.
    - Use its ref_id to match a recording's start_sound_path (or start_combined_path).
    - If that fails and we have seg_end, do the same with end_hits vs end_sound_path.
    """

    if not recordings:
        return None

    # 1) nearest start hit around segment start
    start_anchor = _find_nearest_hit(seg_start, start_hits, _TIME_TOL)
    candidates: List[Dict] = []

    if start_anchor:
        ref_id = str(start_anchor.get("ref_id") or "").lower()
        if ref_id:
            for rec in recordings:
                r_start = _basename(rec.get("start_sound_path")) or _basename(
                    rec.get("start_combined_path")
                )
                if r_start and r_start.lower() == ref_id:
                    candidates.append(rec)

    # 2) fallback: use end anchor near seg_end if needed
    if not candidates and seg_end is not None:
        end_anchor = _find_nearest_hit(seg_end, end_hits, _TIME_TOL)
        if end_anchor:
            ref_id = str(end_anchor.get("ref_id") or "").lower()
            if ref_id:
                for rec in recordings:
                    r_end = _basename(rec.get("end_sound_path")) or _basename(
                        rec.get("end_combined_path")
                    )
                    if r_end and r_end.lower() == ref_id:
                        candidates.append(rec)

    if not candidates:
        logger.debug(
            "align_service: no recording matched for segment at %.3fs (start ref=%s, end ref=%s)",
            seg_start,
            start_anchor.get("ref_id") if start_anchor else None,
            None,
        )
        return None

    # For now, just pick the first candidate; if needed we can add scoring later.
    return candidates[0]
