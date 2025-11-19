from __future__ import annotations

import wave
from pathlib import Path

import numpy as np
from scipy.signal import butter, filtfilt, fftconvolve

DEFAULT_FS = 48_000
DEFAULT_FADE_MS = 8


def fade(signal: np.ndarray, ms: int = DEFAULT_FADE_MS, fs: int = DEFAULT_FS) -> np.ndarray:
    data = np.array(signal, dtype=np.float32, copy=True)
    if data.size == 0:
        return data
    n = max(1, int(ms * fs / 1000))
    n = min(n, data.size)
    ramp = np.linspace(0.0, 1.0, n, dtype=np.float32)
    data[:n] *= ramp
    data[-n:] *= ramp[::-1]
    return data


def _bandpass(payload: np.ndarray, fs: int, low_hz: float = 800.0, high_hz: float = 3500.0) -> np.ndarray:
    nyq = fs / 2.0
    b, a = butter(3, [low_hz / nyq, high_hz / nyq], btype="band")
    return filtfilt(b, a, payload)


def read_wav_mono(path: str | Path, *, apply_bandpass: bool = True) -> tuple[np.ndarray, int]:
    source = Path(path)
    with wave.open(str(source), "rb") as handle:
        fs = handle.getframerate()
        channels = handle.getnchannels()
        sample_width = handle.getsampwidth()
        n_frames = handle.getnframes()
        payload = handle.readframes(n_frames)

    if sample_width == 1:
        data = (np.frombuffer(payload, np.uint8).astype(np.float32) - 128.0) / 128.0
    elif sample_width == 2:
        data = np.frombuffer(payload, np.int16).astype(np.float32) / 32768.0
    else:
        data = np.frombuffer(payload, np.int32).astype(np.float32) / (2**31)

    if channels > 1:
        data = data.reshape(-1, channels).mean(axis=1)

    if apply_bandpass and len(data):
        data = _bandpass(data, fs)
    return data.astype(np.float32), fs


def _normalize(arr: np.ndarray) -> np.ndarray:
    arr = np.asarray(arr, dtype=np.float32)
    return (arr - np.mean(arr)) / (np.std(arr) + 1e-8)


def xcorr_valid(recording: np.ndarray, reference: np.ndarray) -> np.ndarray:
    rec = _normalize(recording)
    ref = _normalize(reference[::-1])
    corr = fftconvolve(rec, ref, mode="valid")
    corr /= max(1, len(reference))
    return corr.astype(np.float32)


__all__ = ["DEFAULT_FADE_MS", "DEFAULT_FS", "fade", "read_wav_mono", "xcorr_valid"]
