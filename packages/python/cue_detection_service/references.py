from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import numpy as np
from loguru import logger

try:
    from cue_detection import gather_reference_library
except ImportError:  # pragma: no cover - workspace fallback
    from packages.python.cue_detection import gather_reference_library
from music_video_generation.postprocessing.audio_utils import read_wav_mono


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


def load_primary_refs(refs_dir: Path) -> Dict[str, List[Dict]]:
    primary = {"start": [], "end": []}
    canonical_len: Dict[str, int] = {}
    canonical_refs: Dict[str, np.ndarray] = {}
    for kind, filename in (("start", "start.wav"), ("end", "end.wav")):
        path = refs_dir / filename
        if not path.exists():
            continue
        try:
            data, _fs = read_wav_mono(path)
            canonical_len[kind] = len(data)
            canonical_refs[kind] = _prepare_reference(data.copy())
            primary[kind].append({"id": filename, "samples": canonical_refs[kind]})
        except Exception as exc:
            logger.warning("primary-cues: failed to load %s: %s", path, exc)

    recent_limits = {"start": 8, "end": 8}
    patterns = {"start": "start_*.wav", "end": "stop_*.wav"}
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
                primary[kind].append({"id": wav_path.name, "samples": clip})
            except Exception as exc:
                logger.warning("primary-cues: failed to load %s: %s", wav_path, exc)

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
        "primary-cues: prepared %d start refs, %d end refs",
        len(primary["start"]),
        len(primary["end"]),
    )
    return primary


def load_secondary_refs(refs_dir: Path) -> Dict[str, List[Dict]]:
    return gather_reference_library(refs_dir, include_common_prefix=False)


__all__ = ["load_primary_refs", "load_secondary_refs"]
