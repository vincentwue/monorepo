from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import json
import numpy as np
from loguru import logger

try:
    from cue_detection import gather_reference_library
except ImportError:  # pragma: no cover - workspace fallback
    from packages.python.cue_detection import gather_reference_library

from music_video_generation.postprocessing.audio_utils import read_wav_mono

# ---------------------------------------------------------------------------
# Global metadata registry
# ---------------------------------------------------------------------------

# Maps ref_id (e.g. "start_2025....wav", "end.wav") -> metadata
# {
#   "kind": "start" | "end",
#   "is_fallback": bool,
#   "recording_id": Optional[str],
#   "track_names": List[str],
# }
REF_META: Dict[str, Dict[str, Any]] = {}

# Set of ref_ids that represent generic / fallback end cues (e.g. "end.wav")
FALLBACK_END_IDS: Set[str] = set()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _prepare_reference(data: np.ndarray) -> np.ndarray:
    arr = np.asarray(data, dtype=np.float32)
    peak = float(np.max(np.abs(arr)) or 1.0)
    return arr / peak


def _upsample_segment(data: np.ndarray, target_len: int) -> np.ndarray:
    if target_len <= 0 or len(data) == target_len:
        return data[:target_len]
    if len(data) < target_len:
        x_old = np.linspace(0.0, 1.0, num=len(data), endpoint=False, dtype=np.float32)
        x_new = np.linspace(0.0, 1.0, num=target_len, endpoint=False, dtype=np.float32)
        upsampled = np.interp(x_new, x_old, data.astype(np.float32))
        return upsampled.astype(np.float32)
    return data[:target_len]


def _load_recording_meta(project_root: Optional[Path]) -> Dict[str, Dict[str, Any]]:
    """
    Load mapping from cue file basename -> recording metadata.

    Returns: { "start_...wav": {"recording_id": "...", "track_names": [...]}, ... }
    """
    if project_root is None:
        return {}

    rec_path = project_root / "recordings.json"
    if not rec_path.exists():
        return {}

    try:
        payload = json.loads(rec_path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("primary-cues: failed to parse recordings.json at %s: %s", rec_path, exc)
        return {}

    mapping: Dict[str, Dict[str, Any]] = {}
    for rec in payload.get("recordings", []):
        rec_id = rec.get("id")
        tracks = rec.get("recording_track_names") or []
        for key in ("start_sound_path", "end_sound_path", "start_combined_path", "end_combined_path"):
            path_str = rec.get(key)
            if not path_str:
                continue
            name = Path(path_str).name
            mapping[name] = {
                "recording_id": rec_id,
                "track_names": list(tracks),
            }
    return mapping


# ---------------------------------------------------------------------------
# Primary / secondary refs
# ---------------------------------------------------------------------------


def load_primary_refs(refs_dir: Path, project_root: Optional[Path] = None) -> Dict[str, List[Dict]]:
    """
    Build the primary reference set (start/stop cues) and populate REF_META / FALLBACK_END_IDS.

    - Canonical "start.wav" / "end.wav" are treated as generic fallbacks.
    - Project-specific cues start_*.wav / stop_*.wav are linked to recordings.json entries.
    """
    global REF_META, FALLBACK_END_IDS

    REF_META = {}
    FALLBACK_END_IDS = set()

    primary: Dict[str, List[Dict]] = {"start": [], "end": []}
    canonical_len: Dict[str, int] = {}
    canonical_refs: Dict[str, np.ndarray] = {}

    # Load canonical fallback refs (start.wav / end.wav)
    for kind, filename in (("start", "start.wav"), ("end", "end.wav")):
        path = refs_dir / filename
        if not path.exists():
            continue
        try:
            data, _fs = read_wav_mono(path)
            canonical_len[kind] = len(data)
            canonical_refs[kind] = _prepare_reference(data.copy())
            entry = {"id": filename, "samples": canonical_refs[kind]}
            primary[kind].append(entry)
            # Fallback meta
            REF_META[filename] = {
                "kind": kind,
                "is_fallback": True,
                "recording_id": None,
                "track_names": [],
            }
            if kind == "end":
                FALLBACK_END_IDS.add(filename)
        except Exception as exc:
            logger.warning("primary-cues: failed to load %s: %s", path, exc)

    # Load per-recording metadata (if available)
    rec_meta_by_name = _load_recording_meta(project_root)

    recent_limits = {"start": 8, "end": 8}
    patterns = {"start": "start_*.wav", "end": "stop_*.wav"}

    # Load project-specific start_*.wav / stop_*.wav
    for kind, pattern in patterns.items():
        files = sorted(refs_dir.glob(pattern), key=lambda p: p.stat().st_mtime)
        if not files:
            continue
        limit = recent_limits.get(kind, 4)
        for wav_path in files[-limit:]:
            try:
                data, _fs = read_wav_mono(wav_path)
                clip = data.copy()
                ref_len = canonical_len.get(kind)
                if ref_len:
                    max_len = int(ref_len * 4) or ref_len
                    if len(clip) > max_len:
                        clip = clip[:max_len]
                    elif len(clip) < ref_len:
                        clip = _upsample_segment(clip, target_len=ref_len)
                clip = _prepare_reference(clip)
                ref_id = wav_path.name
                entry = {"id": ref_id, "samples": clip}
                primary[kind].append(entry)

                meta_src = rec_meta_by_name.get(ref_id, {})
                REF_META[ref_id] = {
                    "kind": kind,
                    "is_fallback": False,
                    "recording_id": meta_src.get("recording_id"),
                    "track_names": list(meta_src.get("track_names") or []),
                }
            except Exception as exc:
                logger.warning("primary-cues: failed to load %s: %s", wav_path, exc)

    # Score refs vs canonical and keep the best few
    for kind, entries in primary.items():
        canonical = canonical_refs.get(kind)
        if canonical is None:
            continue
        for entry in entries:
            samples = entry["samples"]
            if len(samples) == 0:
                entry["score"] = 0.0
                continue
            overlap = min(len(samples), len(canonical))
            if overlap == 0:
                entry["score"] = 0.0
                continue
            canon_slice = canonical[:overlap]
            canon_norm = np.linalg.norm(canon_slice) or 1.0
            correlation = float(np.dot(samples[:overlap], canon_slice) / canon_norm)
            entry["score"] = correlation
        entries.sort(key=lambda e: e.get("score", 0.0), reverse=True)
        limit = recent_limits.get(kind, 8)
        if len(entries) > limit:
            primary[kind] = entries[:limit]

    logger.info(
        "primary-cues: prepared %d start refs, %d end refs (fallback_end_ids=%s)",
        len(primary["start"]),
        len(primary["end"]),
        ",".join(sorted(FALLBACK_END_IDS)) or "none",
    )
    return primary


def load_secondary_refs(refs_dir: Path, project_root: Optional[Path] = None) -> Dict[str, List[Dict]]:
    # project_root is currently unused but kept for symmetry / future use
    return gather_reference_library(refs_dir, include_common_prefix=False)


__all__ = ["load_primary_refs", "load_secondary_refs", "REF_META", "FALLBACK_END_IDS"]
