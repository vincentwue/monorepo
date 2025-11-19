from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Sequence

import numpy as np

from .audio import fade, read_wav_mono, xcorr_valid, DEFAULT_FS


MEDIA_SAMPLE_RATE = DEFAULT_FS


def classify_reference_name(name: str) -> str | None:
    lowered = name.lower()
    if any(token in lowered for token in ("stop", "end")):
        return "end"
    if any(token in lowered for token in ("start", "begin", "cue_start")):
        return "start"
    return None


def gather_reference_library(
    refs_dir: Path,
    *,
    include_common_prefix: bool = True,
) -> Dict[str, List[Dict]]:
    refs: Dict[str, List[Dict]] = {"start": [], "end": []}

    start_common = end_common = None
    start_common_len = end_common_len = 0
    try:
        start_common, fs = read_wav_mono(refs_dir / "start.wav")
        start_common = fade(start_common, fs=fs)
        start_common_len = len(start_common)
    except Exception:
        print("[warn] start.wav not found or unreadable")

    try:
        end_common, fs = read_wav_mono(refs_dir / "end.wav")
        end_common = fade(end_common, fs=fs)
        end_common_len = len(end_common)
    except Exception:
        print("[warn] end.wav not found or unreadable")

    for wav in sorted(refs_dir.glob("*.wav")):
        name = wav.name.lower()
        kind = classify_reference_name(name)
        if not kind or name in {"start.wav", "end.wav"}:
            continue
        try:
            data, fs = read_wav_mono(wav)
            composite = data
            appended_prefix = trimmed_prefix = False
            if include_common_prefix:
                if (
                    kind == "start"
                    and start_common is not None
                    and start_common_len
                    and len(data) <= int(start_common_len * 1.2)
                ):
                    composite = np.concatenate([start_common, data])
                    appended_prefix = True
                elif (
                    kind == "end"
                    and end_common is not None
                    and end_common_len
                    and len(data) <= int(end_common_len * 1.2)
                ):
                    composite = np.concatenate([end_common, data])
                    appended_prefix = True
            else:
                if kind == "start" and start_common_len and len(data) > start_common_len:
                    composite = data[start_common_len:]
                    trimmed_prefix = True
                elif kind == "end" and end_common_len and len(data) > end_common_len:
                    composite = data[end_common_len:]
                    trimmed_prefix = True

            composite = fade(composite.copy(), ms=16, fs=fs)
            refs[kind].append(
                {
                    "id": wav.name,
                    "samples": composite,
                    "mtime": wav.stat().st_mtime,
                }
            )
            seconds = len(data) / float(fs or MEDIA_SAMPLE_RATE)
            print(
                f"[debug] ref {wav.name} kind={kind} len={seconds:.3f}s prefix_added={appended_prefix} prefix_trimmed={trimmed_prefix}"
            )
        except Exception as exc:
            print(f"[warn] Failed to load {wav}: {exc}")

    def _keep_recent(entries: List[Dict], limit: int = 40) -> List[Dict]:
        if not entries:
            return entries
        entries.sort(key=lambda r: r.get("mtime", 0))
        trimmed = entries[-limit:]
        for entry in trimmed:
            entry.pop("mtime", None)
        return trimmed

    refs["start"] = _keep_recent(refs["start"])
    refs["end"] = _keep_recent(refs["end"])

    print(f"[info] Using start cues: {[r['id'] for r in refs['start']]}")
    print(f"[info] Using end cues:   {[r['id'] for r in refs['end']]}")
    return refs


def find_all_matches(ref: np.ndarray, rec: np.ndarray, threshold: float, min_sep_s: float) -> List[tuple[int, float]]:
    corr = xcorr_valid(rec, ref)
    max_corr = float(np.max(corr))
    if max_corr < 0.01:
        return []
    adaptive_base = min(max(threshold, 0.0), max_corr)
    adaptive_thresh = max(adaptive_base * 0.9, max_corr * 0.55)
    nms = int(max(1, round(min_sep_s * MEDIA_SAMPLE_RATE)))
    peaks: List[tuple[int, float]] = []
    i = 0
    while i < len(corr):
        if corr[i] >= adaptive_thresh:
            j_end = min(len(corr), i + nms)
            j = i + int(np.argmax(corr[i:j_end]))
            peaks.append((j, float(corr[j])))
            i = j + nms
        else:
            i += 1

    if len(peaks) == 0 or len(peaks) > 2:
        print(f"[debug] peaks={len(peaks)}, max_corr={np.max(corr):.3f}")
    return peaks


def deduplicate_hits(hits: Sequence[Dict], tol_s: float = 0.2) -> List[Dict]:
    if not hits:
        return []
    ordered = sorted(hits, key=lambda h: h["time_s"])
    deduped = [ordered[0]]
    for hit in ordered[1:]:
        if abs(hit["time_s"] - deduped[-1]["time_s"]) > tol_s:
            deduped.append(hit)
    return deduped


def compute_matches(rec: np.ndarray, refs: Dict[str, List[Dict]], threshold: float, min_gap_s: float) -> Dict[str, List[Dict]]:
    results = {"start": [], "end": []}
    for kind, ref_list in refs.items():
        for ref in ref_list:
            hits = find_all_matches(ref["samples"], rec, threshold, min_gap_s)
            for idx, score in hits:
                results[kind].append(
                    {
                        "time_s": idx / MEDIA_SAMPLE_RATE,
                        "score": score,
                        "ref_id": ref["id"],
                    }
                )
    for kind, entries in results.items():
        entries.sort(key=lambda h: h["time_s"])
        results[kind] = deduplicate_hits(entries)
    return results


def build_segments(start_hits: Sequence[Dict], end_hits: Sequence[Dict], total_duration: float) -> List[Dict]:
    segments: List[Dict] = []
    i = j = 0
    while i < len(start_hits):
        start_t = start_hits[i]["time_s"]
        end_t = None
        if j < len(end_hits):
            candidate = end_hits[j]["time_s"]
            if candidate <= start_t:
                j += 1
                continue
            end_t = candidate
        segments.append(
            {
                "index": len(segments) + 1,
                "start_time_s": start_t,
                "end_time_s": end_t,
                "duration_s": (end_t - start_t) if end_t else None,
                "edge_case": None if end_t else "missing_end",
            }
        )
        i += 1
        j += 1
    return segments


__all__ = [
    "build_segments",
    "classify_reference_name",
    "compute_matches",
    "deduplicate_hits",
    "find_all_matches",
    "gather_reference_library",
]
