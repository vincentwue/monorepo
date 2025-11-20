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
    """
    Performs "secondary" matching around already-found primary anchors.

    We take the primary cue (high-threshold) as the anchor, then scan a
    small window around it for lower-threshold variants (e.g. different
    channels, slightly different renders, etc.).
    """

    # Time windows around the primary anchors where we look for secondary hits.
    START_WINDOW_PRE_S = 0.4
    START_WINDOW_POST_S = 1.4
    END_WINDOW_PRE_S = 1.4
    END_WINDOW_POST_S = 0.4

    # Minimum gap between hits (seconds).
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
        """
        Scan a time window around anchor_time for matches to the given refs.
        """
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

        # De-duplicate close hits and sort by score.
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
        """
        For each primary anchor, find a bucket of nearby secondary hits.
        """
        window_pre, window_post = self.start_window if is_start else self.end_window
        buckets: List[List[Dict]] = []
        for anchor in anchors:
            hits = self._scan_window(rec, refs, anchor.get("time_s"), window_pre, window_post, threshold)
            buckets.append(hits)
        return buckets


def _is_fallback_end(hit: Dict) -> bool:
    """
    Return True if this end hit corresponds to the generic fallback marker
    (e.g. 'end.wav'), which should only be used when no project-specific
    end cue is available.
    """
    ref = str(hit.get("ref_id", "")).lower()
    # You can extend this if you ever introduce other generic "safety" refs.
    return ref == "end.wav"


def build_pairs(
    segments: List[Dict],
    start_hits: List[Dict],
    end_hits: List[Dict],
    start_secondary: List[List[Dict]],
    end_secondary: List[List[Dict]],
) -> List[Dict]:
    """
    Build (start, end) cue pairs for each detected segment.

    Key behaviour:
      - Start anchor: we still map segment #i -> start_hits[i-1] (if present).
      - End anchor: we look at ALL end_hits that fall inside the segment's
        [start_time_s, end_time_s] window and choose:
            1) The highest-scoring NON-fallback end cue (e.g. 'stop_*.wav'),
               if any exist in that window.
            2) Otherwise, if only fallback hits (like 'end.wav') exist,
               we pick the best fallback.
            3) If nothing matches, end_anchor stays None (segment is open).
      - Secondary hits:
          * start_secondary[i-1] stays attached to the i-th segment.
          * end_secondary is indexed by the chosen end hit in end_hits.
    """
    pairs: List[Dict] = []

    for idx, segment in enumerate(segments, start=1):
        seg_start = float(segment["start_time_s"])
        seg_end = segment.get("end_time_s")
        seg_end = float(seg_end) if seg_end is not None else None

        # Start anchor: simple positional mapping.
        start_anchor = start_hits[idx - 1] if idx - 1 < len(start_hits) else None

        # Collect all end hits that fall inside this segment's time window.
        candidates: List[Dict] = []
        for eh in end_hits:
            t = float(eh.get("time_s", 0.0))
            if t < seg_start:
                continue
            if seg_end is not None and t > seg_end + 0.05:
                # Slight tolerance to catch hits right at the boundary.
                continue
            candidates.append(eh)

        # Choose the best end candidate with "non-fallback first" policy.
        end_anchor = None
        if candidates:
            non_fallback = [h for h in candidates if not _is_fallback_end(h)]
            if non_fallback:
                end_anchor = max(non_fallback, key=lambda h: float(h.get("score", 0.0)))
            else:
                # Only fallback(s) in this window; pick the strongest one.
                end_anchor = max(candidates, key=lambda h: float(h.get("score", 0.0)))

        # Secondary hits for start and end.
        start_sec_hits = start_secondary[idx - 1] if idx - 1 < len(start_secondary) else []

        if end_anchor is not None:
            try:
                end_idx = end_hits.index(end_anchor)
            except ValueError:
                end_sec_hits = []
            else:
                end_sec_hits = end_secondary[end_idx] if end_idx < len(end_secondary) else []
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
                "window_start_s": seg_start,
                "window_end_s": seg_end,
            }
        )

    return pairs


__all__ = ["SecondaryMatcher", "build_pairs"]
