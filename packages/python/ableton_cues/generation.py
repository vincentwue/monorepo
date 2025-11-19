from __future__ import annotations

import os
import time
import wave
from pathlib import Path

import numpy as np

FS = 48000
PEAK = 10 ** (-0 / 20)
FADE_MS = 8
REF_DIR = "cue_refs"
START_NAME = "start"
END_NAME = "end"


def _fade(x: np.ndarray, ms: int = FADE_MS, fs: int = FS) -> np.ndarray:
    n = max(1, int(ms * fs / 1000))
    r = np.linspace(0, 1, n, dtype=np.float32)
    x[:n] *= r
    x[-n:] *= r[::-1]
    return x


def _tone(freq: float, dur: float, fs: int = FS) -> np.ndarray:
    t = np.linspace(0, dur, int(fs * dur), endpoint=False, dtype=np.float32)
    return np.sin(2 * np.pi * freq * t)


def _chirp_up(f0: float, f1: float, dur: float, fs: int = FS) -> np.ndarray:
    t = np.linspace(0, dur, int(fs * dur), endpoint=False, dtype=np.float32)
    k = np.log(f1 / f0) / dur
    phase = 2 * np.pi * f0 * (np.expm1(k * t) / k)
    return np.sin(phase)


def _chirp_down(f0: float, f1: float, dur: float, fs: int = FS) -> np.ndarray:
    t = np.linspace(0, dur, int(fs * dur), endpoint=False, dtype=np.float32)
    k = np.log(f1 / f0) / dur
    phase = 2 * np.pi * f0 * (np.expm1(k * t) / k)
    return np.sin(phase)


def _mk_cue() -> np.ndarray:
    x = np.concatenate(
        [
            _tone(800, 0.08),
            np.zeros(int(0.04 * FS), np.float32),
            _tone(1600, 0.08),
            np.zeros(int(0.08 * FS), np.float32),
            _chirp_up(600, 5000, 0.22),
        ]
    )
    return _fade(x, ms=6)


def mk_start_cue() -> np.ndarray:
    return _mk_cue()


def mk_end_cue() -> np.ndarray:
    cue = _mk_cue()
    return cue[::-1].copy()


def _to_stereo(mono: np.ndarray) -> np.ndarray:
    y = np.clip(mono * PEAK, -1, 1).astype(np.float32)
    return np.column_stack((y, y))


def _stereo_pcm_bytes(stereo_f32: np.ndarray) -> bytes:
    pcm16 = (np.clip(stereo_f32, -1, 1) * 32767).astype(np.int16)
    return pcm16.tobytes()


def _save_wav(path: str, pcm_bytes: bytes) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(FS)
        wf.writeframes(pcm_bytes)


def ensure_refs(ref_dir: str | os.PathLike[str] | None = None):
    target_dir = Path(ref_dir) if ref_dir else Path(REF_DIR)
    target_dir.mkdir(parents=True, exist_ok=True)
    start_f32 = _to_stereo(mk_start_cue())
    end_f32 = _to_stereo(mk_end_cue())
    start_pcm = _stereo_pcm_bytes(start_f32)
    end_pcm = _stereo_pcm_bytes(end_f32)
    start_path = target_dir / f"{START_NAME}.wav"
    end_path = target_dir / f"{END_NAME}.wav"
    _save_wav(str(start_path), start_pcm)
    _save_wav(str(end_path), end_pcm)
    return str(start_path), str(end_path), start_f32, end_f32, start_pcm, end_pcm


def mk_stop_unique(total_dur: float = 1.2, seed: int | None = None) -> np.ndarray:
    rng = np.random.default_rng(seed or int(time.time() * 1e6))
    parts = [
        _fade(_chirp_down(4600, 200, 0.35, FS)),
        np.zeros(int(0.04 * FS), dtype=np.float32),
        _fade(_tone(rng.uniform(200, 360), 0.18, FS)),
    ]
    tail = rng.standard_normal(int(0.25 * FS)).astype(np.float32)
    tail = _fade(tail * 0.12)
    parts.append(tail)
    x = np.concatenate(parts)
    x = _fade(x)
    x = x / (np.max(np.abs(x)) + 1e-6)
    return x.astype(np.float32)


def ensure_stop_ref(
    filename: str = "stop.wav",
    *,
    ref_dir: str | os.PathLike[str] | None = None,
    seed: int | None = None,
):
    target_dir = Path(ref_dir) if ref_dir else Path(REF_DIR)
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / filename
    mono = mk_stop_unique(seed=seed)
    stereo = _to_stereo(mono)
    _save_wav(str(path), _stereo_pcm_bytes(stereo))
    return str(path), stereo


__all__ = ["ensure_refs", "mk_stop_unique", "ensure_stop_ref"]

