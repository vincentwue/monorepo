from __future__ import annotations

import os
import wave
from pathlib import Path

import numpy as np

from .constants import DEFAULT_PEAK_DB, DEFAULT_SAMPLE_RATE, db_to_linear


def to_stereo(mono: np.ndarray, peak_db: float = DEFAULT_PEAK_DB) -> np.ndarray:
    gain = db_to_linear(peak_db)
    payload = np.clip(np.asarray(mono, dtype=np.float32) * gain, -1.0, 1.0)
    return np.column_stack((payload, payload))


def stereo_to_pcm(stereo: np.ndarray) -> bytes:
    payload = np.clip(np.asarray(stereo, dtype=np.float32), -1.0, 1.0)
    return (payload * 32767).astype(np.int16).tobytes()


def save_wav(path: str | os.PathLike[str], stereo: np.ndarray, *, fs: int = DEFAULT_SAMPLE_RATE) -> Path:
    directory = Path(path).parent
    directory.mkdir(parents=True, exist_ok=True)
    pcm = stereo_to_pcm(stereo)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(2)
        handle.setsampwidth(2)
        handle.setframerate(fs)
        handle.writeframes(pcm)
    return Path(path)


__all__ = ["save_wav", "stereo_to_pcm", "to_stereo"]
