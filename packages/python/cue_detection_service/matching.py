from __future__ import annotations

from typing import Dict, List, Sequence

import numpy as np

try:
    from cue_detection import deduplicate_hits, find_all_matches
except ImportError:  # pragma: no cover - workspace fallback
    from packages.python.cue_detection import deduplicate_hits, find_all_matches

try:
    from cue_detection import DEFAULT_FS as FS
except ImportError:  # pragma: no cover - workspace fallback
    from packages.python.cue_detection import DEFAULT_FS as FS


class SecondaryMatcher:
    START_WINDOW_PRE_S = 0.4
    START_WINDOW_POST_S = 1.4
    END_WINDOW_PRE_S = 1.4
    END_WINDOW_POST_S = 0.4
    SECONDARY_MIN_GAP_S = 0.05

    def __init__(
        self,
        *,
        min_gap_s: float = SECONDARY_MIN_GAP_S,
        start_window: tuple[float, float] | None = None,
        end_window: tuple[float, float] | None = None,
    ) -> None:
        self.min_gap_s = min_gap_s
        self.start_window = start_window or (self.START_WINDOW_PRE_S, self.START_WINDOW_POST_S)
        self.end_window = end_window or (self.END_WINDOW_PRE_S, self.END_WINDOW_POST_S)

    def _scan_window(
        self,
        rec: np.ndarray,
        refs: Sequence[Dict],
        anchor_time: float | None,
        window_pre: float,
        window_post: float,
        threshold: float,
    ) -> List[Dict]:
        if anchor_time is None or not refs:
            return []
        start_t = max(0.0, anchor_time - window_pre)
        end_t = min(len(rec) / FS, anchor_time + window_post)
        if end_t <= start_t:
            return []
        start_idx = int(start_t * FS)
        end_idx = int(end_t * FS)
        segment = rec[start_idx:end_idx]
        if len(segment) == 0:
            return []
        hits: List[Dict] = []
        for ref in refs:
            raw_hits = find_all_matches(ref["samples"], segment, threshold, self.min_gap_s)
            for idx, score in raw_hits:
                hits.append(
                    {
                        "time_s": (start_idx + idx) / FS,
                        "score": score,
                        "ref_id": ref.get("id", ""),
                    }
                )
        hits = deduplicate_hits(hits, tol_s=0.1)
        hits.sort(key=lambda h: h["score"], reverse=True)
        return hits

    def find_secondary_matches(
        self,
        rec: np.ndarray,
        refs: Sequence[Dict],
        anchors: Sequence[Dict],
        *,
        threshold: float,
        is_start: bool,
    ) -> List[List[Dict]]:
        window_pre, window_post = self.start_window if is_start else self.end_window
        buckets: List[List[Dict]] = []
        for anchor in anchors:
            hits = self._scan_window(rec, refs, anchor.get("time_s"), window_pre, window_post, threshold)
            buckets.append(hits)
        return buckets


def build_pairs(
    segments: List[Dict],
    start_hits: List[Dict],
    end_hits: List[Dict],
    start_secondary: List[List[Dict]],
    end_secondary: List[List[Dict]],
) -> List[Dict]:
    pairs: List[Dict] = []
    end_index = 0
    for idx, segment in enumerate(segments, start=1):
        start_anchor = start_hits[idx - 1] if idx - 1 < len(start_hits) else None
        end_anchor = None
        if segment.get("end_time_s") is not None:
            while end_index < len(end_hits):
                candidate = end_hits[end_index]
                end_index += 1
                if candidate.get("time_s", 0.0) >= segment["start_time_s"]:
                    end_anchor = candidate
                    break
        start_sec_hits = start_secondary[idx - 1] if idx - 1 < len(start_secondary) else []
        if end_anchor is not None and 0 <= (end_index - 1) < len(end_secondary):
            end_sec_hits = end_secondary[end_index - 1]
        else:
            end_sec_hits = []
        status = "complete"
        if start_anchor is None:
            status = "missing_start"
        elif end_anchor is None:
            status = "missing_end"
        pairs.append(
            {
                "index": idx,
                "start_anchor": start_anchor,
                "start_secondary_hits": start_sec_hits,
                "end_anchor": end_anchor,
                "end_secondary_hits": end_sec_hits,
                "status": status,
                "window_start_s": segment["start_time_s"],
                "window_end_s": segment.get("end_time_s"),
            }
        )
    return pairs


__all__ = ["SecondaryMatcher", "build_pairs"]
