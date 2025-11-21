from __future__ import annotations

from pathlib import Path
from typing import Tuple, List

import wave
import numpy as np
import matplotlib.pyplot as plt  # if you do not use this here, you can remove it

from scipy.signal import butter, filtfilt, fftconvolve, stft


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


def _bandpass(
    payload: np.ndarray,
    fs: int,
    low_hz: float = 1200.0,
    high_hz: float = 6500.0,
) -> np.ndarray:
    """
    Simple Butterworth bandpass.

    Defaults chosen to match coded-chirp cues (~1.7–5.8 kHz) and typical
    phone/DSLR mic passbands.
    """
    nyq = fs / 2.0
    low = max(10.0, low_hz) / nyq
    high = min(high_hz, nyq * 0.99) / nyq
    if not (0.0 < low < high < 1.0):
        # If something is weird with fs/band, just return payload unchanged.
        return payload.astype(np.float32)

    b, a = butter(3, [low, high], btype="band")
    return filtfilt(b, a, payload).astype(np.float32)


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

    data = data.astype(np.float32)

    if apply_bandpass and len(data):
        data = _bandpass(data, fs)

    return data.astype(np.float32), fs


def _compute_spectrogram(
    x: np.ndarray,
    fs: float,
    n_fft: int,
    hop_length: int,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Compute magnitude spectrogram via STFT.

    Returns:
        mag: (freq_bins, time_frames) float32
        t:   (time_frames,) time axis in seconds
    """
    x = np.asarray(x, dtype=np.float32)
    if x.size == 0:
        return np.zeros((0, 0), dtype=np.float32), np.zeros((0,), dtype=np.float32)

    noverlap = n_fft - hop_length
    f, t, Zxx = stft(
        x,
        fs=fs,
        nperseg=n_fft,
        noverlap=noverlap,
        window="hann",
        boundary=None,
        padded=False,
    )
    mag = np.abs(Zxx).astype(np.float32)
    return mag, t  # mag.shape == (freq_bins, time_frames)


def xcorr_valid_spectrogram(
    rec_spec: np.ndarray,
    ref_spec: np.ndarray,
) -> np.ndarray:
    """
    Cross-correlation in spectrogram domain.

    Both inputs are magnitude spectrograms (freq_bins x time_frames).
    We slide ref_spec over rec_spec along the time axis and compute
    a normalized dot-product at each frame position.
    """
    rec_spec = np.asarray(rec_spec, dtype=np.float32)
    ref_spec = np.asarray(ref_spec, dtype=np.float32)

    if rec_spec.ndim != 2 or ref_spec.ndim != 2:
        raise ValueError("Expected 2D spectrograms: (freq_bins, time_frames)")

    F_rec, T_rec = rec_spec.shape
    F_ref, T_ref = ref_spec.shape

    if F_rec != F_ref:
        raise ValueError(f"Frequency bins mismatch: rec={F_rec}, ref={F_ref}")
    if T_rec < T_ref:
        return np.zeros((0,), dtype=np.float32)

    # Flatten reference template
    template = ref_spec.reshape(-1)
    template_norm = np.linalg.norm(template) + 1e-9
    template = template / template_norm

    from numpy.lib.stride_tricks import sliding_window_view

    # windows: (freq_bins, num_positions, T_ref)
    windows = sliding_window_view(rec_spec, T_ref, axis=1)
    F, num_pos, win_len = windows.shape  # win_len == T_ref

    # Flatten windows: (F * T_ref, num_positions)
    win_flat = windows.reshape(F * win_len, num_pos)

    # L2 normalize each window vector
    norms = np.linalg.norm(win_flat, axis=0) + 1e-9
    win_flat_normed = win_flat / norms

    # Correlation = dot(template, window) per position
    corr = template @ win_flat_normed  # (num_positions,)
    return corr.astype(np.float32)


def xcorr_valid(
    x: np.ndarray,
    y: np.ndarray,
) -> np.ndarray:
    """
    1D cross-correlation (valid mode) using FFT convolution.

    corr[k] = sum_n x[n + k] * y[n], with k such that y fully overlaps x.

    Assumes x is the longer array (recording) and y is the shorter (reference).
    """
    x = np.asarray(x, dtype=np.float32)
    y = np.asarray(y, dtype=np.float32)

    if x.size == 0 or y.size == 0:
        return np.zeros((0,), dtype=np.float32)

    # fftconvolve with reversed y gives correlation
    corr_full = fftconvolve(x, y[::-1], mode="valid")
    return corr_full.astype(np.float32)


__all__ = [
    "DEFAULT_FADE_MS",
    "DEFAULT_FS",
    "fade",
    "read_wav_mono",
    "_compute_spectrogram",
    "xcorr_valid_spectrogram",
    "xcorr_valid",
]
