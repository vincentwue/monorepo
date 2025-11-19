from __future__ import annotations

import time
from typing import Optional

import numpy as np

from .constants import DEFAULT_FADE_MS, DEFAULT_SAMPLE_RATE


def fade(signal: np.ndarray, ms: int = DEFAULT_FADE_MS, fs: int = DEFAULT_SAMPLE_RATE) -> np.ndarray:
    arr = np.array(signal, dtype=np.float32, copy=True)
    if arr.size == 0:
        return arr
    n = max(1, int(ms * fs / 1000))
    n = min(n, arr.size)
    ramp = np.linspace(0.0, 1.0, n, dtype=np.float32)
    arr[:n] *= ramp
    arr[-n:] *= ramp[::-1]
    return arr


def _tone(freq: float, duration_s: float, fs: int) -> np.ndarray:
    t = np.linspace(0.0, duration_s, int(fs * duration_s), endpoint=False, dtype=np.float32)
    return np.sin(2 * np.pi * freq * t).astype(np.float32)


def _chirp_up(f0: float, f1: float, duration_s: float, fs: int) -> np.ndarray:
    t = np.linspace(0.0, duration_s, int(fs * duration_s), endpoint=False, dtype=np.float32)
    k = np.log(f1 / f0) / duration_s
    phase = 2 * np.pi * f0 * (np.expm1(k * t) / k)
    return np.sin(phase).astype(np.float32)


def _chirp_down(f0: float, f1: float, duration_s: float, fs: int) -> np.ndarray:
    t = np.linspace(0.0, duration_s, int(fs * duration_s), endpoint=False, dtype=np.float32)
    k = np.log(f1 / f0) / duration_s
    phase = 2 * np.pi * f0 * (np.expm1(k * t) / k)
    return np.sin(phase).astype(np.float32)


def _primary_template(fs: int) -> np.ndarray:
    cue = np.concatenate(
        [
            _tone(800.0, 0.08, fs),
            np.zeros(int(0.04 * fs), dtype=np.float32),
            _tone(1600.0, 0.08, fs),
            np.zeros(int(0.08 * fs), dtype=np.float32),
            _chirp_up(600.0, 5000.0, 0.22, fs),
        ]
    )
    return fade(cue, ms=6, fs=fs)


def start_cue(fs: int = DEFAULT_SAMPLE_RATE) -> np.ndarray:
    return _primary_template(fs)


def end_cue(fs: int = DEFAULT_SAMPLE_RATE) -> np.ndarray:
    cue = _primary_template(fs)
    return cue[::-1].copy()


def stop_cue(total_dur: float = 1.2, seed: Optional[int] = None, fs: int = DEFAULT_SAMPLE_RATE) -> np.ndarray:
    rng = np.random.default_rng(seed or int(time.time() * 1e6))
    parts = [
        fade(_chirp_down(4600.0, 200.0, 0.35, fs), fs=fs),
        np.zeros(int(0.04 * fs), dtype=np.float32),
        fade(_tone(rng.uniform(200.0, 360.0), 0.18, fs), fs=fs),
    ]
    tail = rng.standard_normal(int(0.25 * fs)).astype(np.float32)
    tail = fade(tail * 0.12, fs=fs)
    parts.append(tail)
    cue = np.concatenate(parts)
    cue = fade(cue, fs=fs)
    cue /= np.max(np.abs(cue)) + 1e-6
    return cue.astype(np.float32)


def unique_cue(seed: int, length: float = 1.3, fs: int = DEFAULT_SAMPLE_RATE) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n_total = int(length * fs)
    t = np.linspace(0, length, n_total, endpoint=False, dtype=np.float32)
    blues = np.array([220.0, 261.63, 293.66, 311.13, 329.63, 392.0])
    note_pool = np.concatenate([blues, blues * 2, blues * 0.5])
    tone = np.zeros_like(t)
    num_notes = rng.integers(3, 6)
    note_starts = np.sort(rng.choice(np.linspace(0, length - 0.2, 20), num_notes, replace=False))
    note_durs = rng.uniform(0.05, 0.25, size=num_notes)
    for idx in range(num_notes):
        start_t = note_starts[idx]
        dur = float(note_durs[idx])
        freq = rng.choice(note_pool) * rng.uniform(0.9, 1.1)
        note_t = np.linspace(0.0, dur, int(fs * dur), endpoint=False)
        waveform = np.sin(2 * np.pi * freq * note_t) * (
            0.5 + 0.5 * np.sin(2 * np.pi * rng.uniform(2.0, 5.0) * note_t)
        )
        waveform += 0.3 * np.sin(2 * np.pi * 2 * freq * note_t)
        waveform = fade(waveform, ms=DEFAULT_FADE_MS, fs=fs)
        if rng.random() < 0.4:
            waveform[: int(0.01 * fs)] += rng.standard_normal(int(0.01 * fs)) * 0.1
        start_idx = int(start_t * fs)
        end_idx = min(start_idx + len(waveform), n_total)
        tone[start_idx:end_idx] += waveform[: end_idx - start_idx]
    tone = fade(tone, ms=DEFAULT_FADE_MS * 2, fs=fs)
    tone /= np.max(np.abs(tone) + 1e-6)
    if rng.random() < 0.5:
        tone = np.convolve(tone, np.hanning(64) / 64, mode="same")
    else:
        smooth = np.convolve(tone, np.hanning(64) / 64, mode="same")
        tone -= smooth * 0.2
    return tone.astype(np.float32)


def barker_bpsk(chip_ms: float = 18.0, carrier_hz: float = 3000.0, fs: int = DEFAULT_SAMPLE_RATE) -> np.ndarray:
    barker = np.array([+1, +1, +1, +1, +1, -1, -1, +1, +1, -1, +1, -1, +1], dtype=np.float32)
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
