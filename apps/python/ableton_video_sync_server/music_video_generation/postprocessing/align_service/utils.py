from __future__ import annotations

from typing import Dict, Optional, Sequence


def find_start_cue(entry: Dict) -> Optional[float]:
    """
    Use the first start hit as the cue position within this media file.
    Fallback: first segment start_time_s.
    """
    hits: Sequence[Dict] = entry.get("start_hits") or []
    for hit in hits:
        t = hit.get("time_s")
        if isinstance(t, (int, float)):
            return float(t)

    segments: Sequence[Dict] = entry.get("segments") or []
    if segments:
        t = segments[0].get("start_time_s")
        if isinstance(t, (int, float)):
            return float(t)

    return None
