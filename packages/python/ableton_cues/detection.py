from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import numpy as np
from scipy.signal import fftconvolve

from music_video_generation.postprocessing.audio_utils import fade, read_wav_mono, xcorr_valid
from music_video_generation.postprocessing.config import FADE_MS, FS


def classify_reference_name(name: str) -> str | None:
    n = name.lower()
    if "stop" in n or "end" in n:
        return "end"
    if "start" in n or "begin" in n or "cue_start" in n:
        return "start"
    return None


def gather_reference_library(refs_dir: Path, *, include_common_prefix: bool = True) -> Dict[str, List[Dict]]:
    refs: Dict[str, List[Dict]] = {"start": [], "end": []}

    start_common, end_common = None, None
    try:
        start_common, fs = read_wav_mono(refs_dir / "start.wav")
        start_common = fade(start_common, fs=fs)
    except Exception:
        print("[warn] start.wav not found or unreadable")

    try:
        end_common, fs = read_wav_mono(refs_dir / "end.wav")
        end_common = fade(end_common, fs=fs)
    except Exception:
        print("[warn] end.wav not found or unreadable")

    for wav in sorted(refs_dir.glob("*.wav")):
        name = wav.name.lower()
        kind = classify_reference_name(name)
        if not kind or name in ("start.wav", "end.wav"):
            continue
        try:
            data, fs = read_wav_mono(wav)
            if include_common_prefix and kind == "start" and start_common is not None:
                composite = np.concatenate([start_common, data])
            elif include_common_prefix and kind == "end" and end_common is not None:
                composite = np.concatenate([end_common, data])
            else:
                composite = data

            composite = fade(composite.copy(), ms=FADE_MS * 2, fs=fs)
            refs[kind].append(
                {
                    "id": wav.name,
                    "samples": composite,
                    "mtime": wav.stat().st_mtime,
                }
            )
        except Exception as exc:
            print(f"[warn] Failed to load {wav}: {exc}")

    def _keep_recent(ref_list: List[Dict], limit: int = 40) -> List[Dict]:
        if not ref_list:
            return ref_list
        ref_list.sort(key=lambda r: r.get("mtime", 0))
        trimmed = ref_list[-limit:]
        for entry in trimmed:
            entry.pop("mtime", None)
        return trimmed

    refs["start"] = _keep_recent(refs["start"])
    refs["end"] = _keep_recent(refs["end"])

    start_ids = [r["id"] for r in refs["start"]]
    end_ids = [r["id"] for r in refs["end"]]
    print(f"[info] Using start cues: {start_ids}")
    print(f"[info] Using end cues:   {end_ids}")
    return refs


def find_all_matches(ref, rec, threshold, min_sep_s):
    cor = xcorr_valid(rec, ref)
    max_corr = np.max(cor)
    if max_corr < threshold * 0.5:
        return []
    adaptive_thresh = max(threshold * 0.9, max_corr * 0.7)
    nms = int(max(1, round(min_sep_s * FS)))
    peaks, i = [], 0
    while i < len(cor):
        if cor[i] >= adaptive_thresh:
            j_end = min(len(cor), i + nms)
            j = i + int(np.argmax(cor[i:j_end]))
            peaks.append((j, float(cor[j])))
            i = j + nms
        else:
            i += 1

    if len(peaks) == 0 or len(peaks) > 2:
        print(f"[debug] peaks={len(peaks)}, max_corr={np.max(cor):.3f}")

    return peaks


def deduplicate_hits(hits, tol_s=0.2):
    if not hits:
        return []
    hits.sort(key=lambda h: h["time_s"])
    deduped = [hits[0]]
    for h in hits[1:]:
        if abs(h["time_s"] - deduped[-1]["time_s"]) > tol_s:
            deduped.append(h)
    return deduped


def compute_matches(rec, refs, threshold, min_gap_s):
    out = {"start": [], "end": []}
    for kind, ref_list in refs.items():
        for ref in ref_list:
            hits = find_all_matches(ref["samples"], rec, threshold, min_gap_s)
            for idx, score in hits:
                out[kind].append(
                    {
                        "time_s": idx / FS,
                        "score": score,
                        "ref_id": ref["id"],
                    }
                )
    for kind in out:
        out[kind].sort(key=lambda h: h["time_s"])
        out[kind] = deduplicate_hits(out[kind])
    return out


def build_segments(start_hits, end_hits, total_duration):
    segs, i, j = [], 0, 0
    while i < len(start_hits):
        start_t = start_hits[i]["time_s"]
        end_t = None
        if j < len(end_hits):
            end_t = end_hits[j]["time_s"]
            if end_t <= start_t:
                j += 1
                continue
        segs.append(
            {
                "index": len(segs) + 1,
                "start_time_s": start_t,
                "end_time_s": end_t,
                "duration_s": (end_t - start_t) if end_t else None,
                "edge_case": None if end_t else "missing_end",
            }
        )
        i += 1
        j += 1
    return segs


__all__ = ["gather_reference_library", "compute_matches", "build_segments", "find_all_matches"]

