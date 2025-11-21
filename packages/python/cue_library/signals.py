from __future__ import annotations

import time
from typing import Optional

import numpy as np

from .constants import DEFAULT_FADE_MS, DEFAULT_SAMPLE_RATE


# ---------------------------------------------------------------------------
# Basic utilities
# ---------------------------------------------------------------------------


def fade(signal: np.ndarray, ms: int = DEFAULT_FADE_MS, fs: int = DEFAULT_SAMPLE_RATE) -> np.ndarray:
    """
    Apply symmetric fade-in / fade-out to a mono signal.
    """
    arr = np.array(signal, dtype=np.float32, copy=True)
    if arr.size == 0:
        return arr
    n = max(1, int(ms * fs / 1000))
    n = min(n, arr.size)
    ramp = np.linspace(0.0, 1.0, n, dtype=np.float32)
    arr[:n] *= ramp
    arr[-n:] *= ramp[::-1]
    return arr


def _pn_sequence(seed: int, length: int) -> np.ndarray:
    """
    Generate a deterministic pseudo-random ±1 sequence for a given seed.

    This is not a true m/Gold code implementation, but for practical purposes
    (cross-correlation between different seeds) it behaves very similarly:
    long, near-orthogonal codes with strong autocorrelation peaks.
    """
    rng = np.random.default_rng(seed)
    bits = rng.integers(0, 2, size=length, dtype=np.int8)
    return np.where(bits > 0, 1.0, -1.0).astype(np.float32)


def _linear_chirp(
    f0: float,
    f1: float,
    duration_s: float,
    fs: int,
) -> np.ndarray:
    """
    Band-limited linear chirp from f0 to f1 over duration_s seconds.
    """
    n = int(fs * duration_s)
    t = np.linspace(0.0, duration_s, n, endpoint=False, dtype=np.float32)
    k = (f1 - f0) / duration_s
    phase = 2.0 * np.pi * (f0 * t + 0.5 * k * t * t)
    return np.sin(phase).astype(np.float32)


def _apply_pn(chirp: np.ndarray, pn: np.ndarray) -> np.ndarray:
    """
    Apply a ±1 PN sequence as a phase (sign) code to the chirp.
    The PN sequence is repeated to cover the whole chirp length.
    """
    if pn.size == 0:
        return chirp

    reps = int(np.ceil(chirp.size / pn.size))
    code = np.tile(pn, reps)[: chirp.size]
    return (chirp * code).astype(np.float32)


def _coded_chirp(
    seed: int,
    duration_s: float,
    fs: int,
    *,
    f0: float = 1700.0,
    f1: float = 5800.0,
    code_length: int = 63,
    fade_ms: int = DEFAULT_FADE_MS * 2,
) -> np.ndarray:
    """
    Core building block: band-limited linear chirp (f0..f1) phase-coded by a
    PN sequence derived from `seed`.

    - seed:       integer seed for PN code (different seeds => near-orthogonal IDs)
    - duration_s: total chirp duration
    - fs:         sample rate
    - f0, f1:     frequency band, chosen to sit safely in phone/mirror responses
    - code_length: length of PN sequence before repetition
    """
    chirp = _linear_chirp(f0=f0, f1=f1, duration_s=duration_s, fs=fs)
    pn = _pn_sequence(seed=seed, length=code_length)
    coded = _apply_pn(chirp, pn)
    coded = fade(coded, ms=fade_ms, fs=fs)

    peak = float(np.max(np.abs(coded)) + 1e-6)
    coded = (coded / peak).astype(np.float32)
    return coded


# ---------------------------------------------------------------------------
# Public cues
# ---------------------------------------------------------------------------


def start_cue(fs: int = DEFAULT_SAMPLE_RATE) -> np.ndarray:
    """
    Primary START cue:
    Short, robust coded chirp with fixed PN seed.

    Duration kept modest for responsiveness; use this for "start.wav".
    """
    # ~250 ms; seed chosen arbitrarily, but fixed.
    return _coded_chirp(seed=1, duration_s=0.25, fs=fs, code_length=63)


def end_cue(fs: int = DEFAULT_SAMPLE_RATE) -> np.ndarray:
    """
    Primary END cue:
    Another short coded chirp with a different PN seed to minimize cross-talk
    with the START cue.
    """
    # ~250 ms; different seed than start_cue.
    return _coded_chirp(seed=2, duration_s=0.25, fs=fs, code_length=63)


def stop_cue(
    total_dur: float = 1.2,
    seed: Optional[int] = None,
    fs: int = DEFAULT_SAMPLE_RATE,
) -> np.ndarray:
    """
    STOP cue:
    Longer coded chirp for extra reliability, wrapped in short silence guards.

    - total_dur: desired total duration in seconds
    - seed:      optional; if None, uses a fixed default
    """
    if total_dur <= 0.1:
        # Degenerate case: just fall back to a short coded chirp
        return _coded_chirp(seed=seed or 99991, duration_s=max(total_dur, 0.08), fs=fs, code_length=63)

    guard_s = 0.02  # 20 ms of silence before and after to survive AGC edges
    body_dur = max(total_dur - 2 * guard_s, 0.08)

    core = _coded_chirp(seed=seed or 99991, duration_s=body_dur, fs=fs, code_length=127)
    guard = np.zeros(int(guard_s * fs), dtype=np.float32)

    cue = np.concatenate([guard, core, guard])
    cue = fade(cue, ms=DEFAULT_FADE_MS * 2, fs=fs)
    peak = float(np.max(np.abs(cue)) + 1e-6)
    cue = (cue / peak).astype(np.float32)
    return cue


def unique_cue(
    seed: int,
    length: float = 1.3,
    fs: int = DEFAULT_SAMPLE_RATE,
) -> np.ndarray:
    """
    UNIQUE cue:
    Seeded, longer coded chirp for per-take / per-event IDs.

    - seed:   determines PN sequence; different seeds => different nearly
              orthogonal IDs.
    - length: duration in seconds; longer = even more robust detection.
    """
    # Use a longer PN code here to further reduce cross-correlation between IDs.
    return _coded_chirp(seed=seed, duration_s=length, fs=fs, code_length=127)


def barker_bpsk(
    chip_ms: float = 18.0,
    carrier_hz: float = 3000.0,
    fs: int = DEFAULT_SAMPLE_RATE,
) -> np.ndarray:
    """
    Legacy / fallback Barker-coded BPSK tone.

    Still useful as a compact, strongly-correlating reference, though the
    coded chirps above are generally more robust against compression and room
    acoustics.
    """
    barker = np.array(
        [+1, +1, +1, +1, +1, -1, -1, +1, +1, -1, +1, -1, +1],
        dtype=np.float32,
    )
    chip_n = max(1, int(round(fs * (chip_ms / 1000.0))))
    t_chip = np.linspace(0.0, chip_ms / 1000.0, chip_n, endpoint=False, dtype=np.float32)
    carrier = np.sin(2 * np.pi * carrier_hz * t_chip).astype(np.float32)

    payload = np.concatenate([(bit * carrier) for bit in barker]).astype(np.float32)
    payload = fade(payload, ms=DEFAULT_FADE_MS, fs=fs)
    peak = float(np.max(np.abs(payload)) + 1e-6)
    return (payload / peak).astype(np.float32)


__all__ = [
    "barker_bpsk",
    "end_cue",
    "fade",
    "start_cue",
    "stop_cue",
    "unique_cue",
]
