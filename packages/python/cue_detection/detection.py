from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Sequence

from loguru import logger
import numpy as np
import matplotlib.pyplot as plt

from .audio import (
    _compute_spectrogram,
    fade,
    read_wav_mono,
    DEFAULT_FS,
    xcorr_valid_spectrogram,
    xcorr_valid,  # ensure this exists in .audio
)

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
    """
    Load cue references from refs_dir.

    NOTE for coded chirps:
      - start.wav / end.wav are already stand-alone robust cues.
      - For purely coded-chirp workflows, you usually want include_common_prefix=False
        so custom refs are used as-is.
    """
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
        # Skip the primary common references themselves
        if not kind or name in {"start.wav", "end.wav"}:
            continue
        try:
            data, fs = read_wav_mono(wav)
            composite = data
            appended_prefix = trimmed_prefix = False

            # For older tone-based workflows, you often wanted prefixes.
            # For the new coded-chirp system, set include_common_prefix=False
            # to keep refs pure.
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
                f"[debug] ref {wav.name} kind={kind} len={seconds:.3f}s "
                f"prefix_added={appended_prefix} prefix_trimmed={trimmed_prefix}"
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


def _slugify(text: str) -> str:
    allowed = []
    for ch in str(text):
        if ch.isalnum():
            allowed.append(ch.lower())
        elif ch in ("-", "_"):
            allowed.append(ch)
        else:
            allowed.append("_")
    slug = "".join(allowed)
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug.strip("_") or "unnamed"


def _plot_correlation_debug(
    corr: np.ndarray,
    t: np.ndarray,
    adaptive_thresh: float,
    peak_indices: List[int],
    max_corr: float,
    *,
    project_dir: Path | str | None,
    ref_label: str,
    rec_label: str,
) -> Path | None:
    """Internal: visualize correlation + matches and save PNG."""
    if corr.size == 0:
        print("[debug] Empty correlation, nothing to plot")
        return None

    if project_dir is None:
        base_dir = Path.cwd()
    else:
        base_dir = Path(project_dir)

    out_dir = base_dir / "debug" / "cue_matches"
    out_dir.mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True)

    if t.size != corr.size:
        t = np.arange(len(corr), dtype=np.float32)
        t = t - t[0]

    ax1 = axes[0]
    ax1.plot(t, corr, label="Correlation", linewidth=1.0)
    ax1.axhline(adaptive_thresh, linestyle="--", label="Adaptive threshold")

    if peak_indices:
        peak_indices_arr = np.array(peak_indices, dtype=int)
        ax1.scatter(t[peak_indices_arr], corr[peak_indices_arr], s=60, label="Detected matches")

    ax1.set_title("find_all_matches – Detected Matches")
    ax1.set_ylabel("Corr value")
    ax1.legend(loc="upper right")
    ax1.grid(True)

    ax2 = axes[1]
    ax2.plot(t, corr, linewidth=1.0, label="Correlation")
    ax2.axhline(adaptive_thresh, linestyle="--", label="Adaptive threshold")

    below = corr < adaptive_thresh
    ax2.fill_between(t, corr, adaptive_thresh, where=below, alpha=0.3, label="Below threshold")

    ax2.set_title("Regions Without Matches (corr < threshold)")
    ax2.set_xlabel("Time")
    ax2.set_ylabel("Corr value")
    ax2.legend(loc="upper right")
    ax2.grid(True)

    plt.tight_layout()

    ref_slug = _slugify(ref_label)
    rec_slug = _slugify(rec_label)

    filename = (
        f"corr_{ref_slug}_in_{rec_slug}"
        f"_thr_{adaptive_thresh:.3f}"
        f"_max_{max_corr:.3f}"
        f"_peaks_{len(peak_indices)}.png"
    )
    out_path = out_dir / filename
    fig.savefig(out_path, dpi=150)
    plt.close(fig)

    print(f"[debug] Saved correlation debug plot to {out_path}")
    return out_path


# Public wrapper (you had this in __all__)
def plot_find_all_matches(
    corr: np.ndarray,
    t: np.ndarray,
    adaptive_thresh: float,
    peak_indices: List[int],
    max_corr: float,
    *,
    project_dir: Path | str | None,
    ref_label: str,
    rec_label: str,
) -> Path | None:
    return _plot_correlation_debug(
        corr=corr,
        t=t,
        adaptive_thresh=adaptive_thresh,
        peak_indices=peak_indices,
        max_corr=max_corr,
        project_dir=project_dir,
        ref_label=ref_label,
        rec_label=rec_label,
    )


# ─────────────────────────────────────────────
# Core: find_all_matches tuned for coded chirps
# ─────────────────────────────────────────────

def _normalize_for_corr(x: np.ndarray) -> np.ndarray:
    """
    DC-removal + peak normalization.

    For coded chirps, this makes the "ideal" correlation peak close to 1.0.
    """
    if x.size == 0:
        return x.astype(np.float32)
    x = x.astype(np.float32)
    x = x - float(np.mean(x))
    peak = float(np.max(np.abs(x)) + 1e-9)
    x = x / peak
    return x


def find_all_matches(
    ref: np.ndarray,
    rec: np.ndarray,
    threshold: float,
    min_sep_s: float,
    *,
    fs: float = 48_000.0,
    use_spectrogram: bool = False,  # default: waveform mode for coded chirps
    debug_plot: bool = False,
    project_dir: Path | str | None = None,
    ref_label: str = "ref",
    rec_label: str = "rec",
    n_fft: int = 2048,
    hop_length: int = 512,
) -> List[tuple[int, float]]:
    """
    Find cue matches via cross-correlation, optionally visualize the correlation.

    For coded chirps, waveform correlation is usually best:
      - ref and rec are normalized (DC-removed, peak normalized)
      - correlation peak for a good match is close to 1.0
      - `threshold` is interpreted as a fraction of the *best* correlation

    Returns:
        List of (sample_index, corr_value).
    """
    # --- prepare signals: this is critical for robust detection ---
    ref_norm = _normalize_for_corr(ref)
    rec_norm = _normalize_for_corr(rec)

    if use_spectrogram:
        logger.info(
            f"find_all_matches: spectrogram correlation "
            f"(fs={fs}, n_fft={n_fft}, hop={hop_length}) for {ref_label} in {rec_label}"
        )
        ref_spec, t_ref = _compute_spectrogram(ref_norm, fs, n_fft, hop_length)
        rec_spec, t_rec = _compute_spectrogram(rec_norm, fs, n_fft, hop_length)
        corr = xcorr_valid_spectrogram(rec_spec, ref_spec)

        if t_rec.size >= corr.size:
            t_axis = t_rec[: corr.size]
        else:
            dt = hop_length / fs
            t_axis = np.arange(corr.size, dtype=np.float32) * dt

        frames_per_second = fs / hop_length
        nms = int(max(1, round(min_sep_s * frames_per_second)))
        idx_to_samples = hop_length
        mode_suffix = "spec"
    else:
        logger.info(f"find_all_matches: waveform correlation for {ref_label} in {rec_label}")
        corr = xcorr_valid(rec_norm, ref_norm)
        if corr.size:
            t_axis = np.arange(corr.size, dtype=np.float32) / fs
        else:
            t_axis = np.zeros((0,), dtype=np.float32)
        nms = int(max(1, round(min_sep_s * fs)))
        idx_to_samples = 1
        mode_suffix = "wave"

    if corr.size == 0:
        if debug_plot:
            print("[debug] Empty correlation, nothing to plot")
        return []

    max_corr = float(np.max(corr))
    if max_corr < 1e-3:
        if debug_plot:
            print("[debug] No correlation above noise level, skipping plot")
        return []

    # --- adaptive threshold tuned for coded chirps ---
    # Interpret `threshold` as "minimum fraction of best plausible match".
    # Clamp to [0, 1]. Also enforce a floor at 0.5 * max_corr.
    frac = float(np.clip(threshold, 0.0, 1.0))
    adaptive_thresh = max(frac * max_corr, max_corr * 0.5)

    peak_indices: List[int] = []
    i = 0
    L = len(corr)

    while i < L:
        if corr[i] >= adaptive_thresh:
            j_end = min(L, i + nms)
            j = i + int(np.argmax(corr[i:j_end]))
            peak_indices.append(j)
            i = j + nms
        else:
            i += 1

    # Map correlation indices back to sample indices
    peaks: List[tuple[int, float]] = [
        (idx * idx_to_samples, float(corr[idx])) for idx in peak_indices
    ]

    if len(peaks) == 0 or len(peaks) > 2:
        print(f"[debug] peaks={len(peaks)}, max_corr={max_corr:.3f}, mode={mode_suffix}")

    if debug_plot:
        _plot_correlation_debug(
            corr=corr,
            t=t_axis,
            adaptive_thresh=adaptive_thresh,
            peak_indices=peak_indices,
            max_corr=max_corr,
            project_dir=project_dir,
            ref_label=f"{ref_label}_{mode_suffix}",
            rec_label=f"{rec_label}_{mode_suffix}",
        )

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


def compute_matches(
    rec: np.ndarray,
    refs: Dict[str, List[Dict]],
    threshold: float,
    min_gap_s: float,
) -> Dict[str, List[Dict]]:
    """
    Compute all start/end matches for a given recording.

    For the new coded-chirp cues, recommended:
      - threshold ~ 0.3–0.6
      - min_gap_s >= cue_length (e.g., 0.4 for 0.25–0.3 s cues)
    """
    results = {"start": [], "end": []}
    for kind, ref_list in refs.items():
        for ref in ref_list:
            hits = find_all_matches(
                ref["samples"],
                rec,
                threshold,
                min_gap_s,
                fs=MEDIA_SAMPLE_RATE,
                use_spectrogram=False,  # coded chirps: waveform mode
                debug_plot=True,
                project_dir=None,
                ref_label=ref["id"],
                rec_label="recording",
            )
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


def build_segments(
    start_hits: Sequence[Dict],
    end_hits: Sequence[Dict],
    total_duration: float,
) -> List[Dict]:
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
    "plot_find_all_matches",
]
