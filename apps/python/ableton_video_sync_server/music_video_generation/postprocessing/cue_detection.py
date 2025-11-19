#!/usr/bin/env python3
"""
Cue Detection Utilities
-----------------------
Builds reference libraries from cue_refs, detects start/end cues
in media recordings, and constructs segment definitions.
"""

import numpy as np
from pathlib import Path
from scipy.signal import fftconvolve
from .audio_utils import read_wav_mono, fade
from .config import FS, FADE_MS

# =============================================================
# === Helper Functions ===
# =============================================================

def classify_reference_name(name: str):
    n = name.lower()
    if "stop" in n or "end" in n:
        return "end"
    if "start" in n or "begin" in n or "cue_start" in n:
        return "start"
    return None


def mk_barker_bpsk(chip_ms: float, carrier_hz: float, fs: int = FS):
    """Generate a fallback Barker-coded tone."""
    barker = np.array([+1, +1, +1, +1, +1, -1, -1, +1, +1, -1, +1, -1, +1], np.float32)
    chip_n = max(1, int(round(fs * (chip_ms / 1000.0))))
    t_chip = np.linspace(0.0, chip_ms / 1000.0, chip_n, endpoint=False)
    carrier = np.sin(2 * np.pi * carrier_hz * t_chip).astype(np.float32)
    parts = [(bit * carrier) for bit in barker]
    return fade(np.concatenate(parts))


# =============================================================
# === Reference Library Construction ===
# =============================================================

def gather_reference_library(refs_dir: Path):
    """
    Builds a reference library of start/end cues.
    Combines the common start/end WAVs with their corresponding
    unique ones (composite = base + unique).

    Only the newest start and end cues are kept.
    """
    refs = {"start": [], "end": []}

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

    # --- load all start/stop cue wavs ---
    for wav in sorted(refs_dir.glob("*.wav")):
        name = wav.name.lower()
        kind = classify_reference_name(name)
        if not kind or name in ("start.wav", "end.wav"):
            continue
        try:
            data, fs = read_wav_mono(wav)
            # Combine with common prefix if available
            if kind == "start" and start_common is not None:
                composite = np.concatenate([start_common, data])
            elif kind == "end" and end_common is not None:
                composite = np.concatenate([end_common, data])
            else:
                composite = data

            composite = fade(composite.copy(), ms=FADE_MS * 2, fs=fs)
            refs[kind].append({"id": wav.name, "samples": composite})
        except Exception as e:
            print(f"[warn] Failed to load {wav}: {e}")

    # --- keep only the newest start/end ref ---
    def _keep_latest(ref_list):
        if not ref_list:
            return ref_list
        ref_list.sort(key=lambda r: r["id"])
        return [ref_list[-1]]

    refs["start"] = _keep_latest(refs["start"])
    refs["end"] = _keep_latest(refs["end"])

    # --- add fallback Barker tones ---
    for kind, freq in (("start", 3200.0), ("end", 2400.0)):
        refs[kind].append({
            "id": f"barker_{kind}",
            "samples": mk_barker_bpsk(18, freq),
        })

    # --- log info ---
    start_ids = [r["id"] for r in refs["start"]]
    end_ids = [r["id"] for r in refs["end"]]
    print(f"[info] Using start cues: {start_ids}")
    print(f"[info] Using end cues:   {end_ids}")
    return refs


# =============================================================
# === Matching ===
# =============================================================

def find_all_matches(ref, rec, threshold, min_sep_s):
    from .config import FS
    from .audio_utils import xcorr_valid
    cor = xcorr_valid(ref, rec)
    max_corr = np.max(cor)
    if max_corr < threshold * 0.5:
        # skip too-low signals altogether
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
    """Collapse hits that occur within ±tol_s seconds."""
    if not hits:
        return []
    hits.sort(key=lambda h: h["time_s"])
    deduped = [hits[0]]
    for h in hits[1:]:
        if abs(h["time_s"] - deduped[-1]["time_s"]) > tol_s:
            deduped.append(h)
    return deduped


def compute_matches(rec, refs, threshold, min_gap_s):
    """Compute matches for start and end cues."""
    out = {"start": [], "end": []}
    for kind, ref_list in refs.items():
        for ref in ref_list:
            hits = find_all_matches(ref["samples"], rec, threshold, min_gap_s)
            for idx, score in hits:
                out[kind].append({
                    "time_s": idx / FS,
                    "score": score,
                    "ref_id": ref["id"],
                })
    # sort + deduplicate
    for kind in out:
        out[kind].sort(key=lambda h: h["time_s"])
        out[kind] = deduplicate_hits(out[kind])
    return out


# =============================================================
# === Segment Building ===
# =============================================================

def build_segments(start_hits, end_hits, total_duration):
    """Pair each start cue with the nearest following end cue."""
    segs, i, j = [], 0, 0
    while i < len(start_hits):
        start_t = start_hits[i]["time_s"]
        end_t = None
        if j < len(end_hits):
            end_t = end_hits[j]["time_s"]
            if end_t <= start_t:
                j += 1
                continue
        segs.append({
            "index": len(segs) + 1,
            "start_time_s": start_t,
            "end_time_s": end_t,
            "duration_s": (end_t - start_t) if end_t else None,
            "edge_case": None if end_t else "missing_end",
        })
        i += 1
        j += 1
    return segs
