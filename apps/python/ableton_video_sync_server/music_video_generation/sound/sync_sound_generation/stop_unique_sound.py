from __future__ import annotations
import os, wave, time
from pathlib import Path
import numpy as np

FS = 48000
REF_DIR = "cue_refs"
FADE_MS = 8


def _fade(x: np.ndarray, ms: int = FADE_MS, fs: int = FS) -> np.ndarray:
    n = max(1, int(ms * fs / 1000))
    r = np.linspace(0, 1, n, dtype=np.float32)
    x[:n] *= r
    x[-n:] *= r[::-1]
    return x


def _tone(freq: float, dur: float, fs: int = FS) -> np.ndarray:
    t = np.linspace(0, dur, int(fs * dur), endpoint=False, dtype=np.float32)
    return np.sin(2 * np.pi * freq * t)


def _chirp_down(f0: float, f1: float, dur: float, fs: int = FS) -> np.ndarray:
    t = np.linspace(0, dur, int(fs * dur), endpoint=False, dtype=np.float32)
    k = np.log(f1 / f0) / dur
    phase = 2 * np.pi * f0 * (np.expm1(k * t) / k)
    return np.sin(phase)


def mk_stop_unique(total_dur: float = 1.2, seed: int | None = None) -> np.ndarray:
    rng = np.random.default_rng(seed or int(time.time() * 1e6))
    parts = []
    parts.append(_fade(_chirp_down(4600, 200, 0.35, FS)))
    parts.append(np.zeros(int(0.04 * FS), dtype=np.float32))
    parts.append(_fade(_tone(rng.uniform(200, 360), 0.18, FS)))
    tail = rng.standard_normal(int(0.25 * FS)).astype(np.float32)
    tail = _fade(tail * 0.12)
    parts.append(tail)
    x = np.concatenate(parts)
    x = _fade(x)
    x = x / (np.max(np.abs(x)) + 1e-6)
    return x.astype(np.float32)


def _to_stereo_float32(mono: np.ndarray) -> np.ndarray:
    y = np.clip(mono, -1, 1).astype(np.float32)
    return np.column_stack((y, y))


def _stereo_pcm_bytes(stereo_f32: np.ndarray) -> bytes:
    return (np.clip(stereo_f32, -1, 1) * 32767).astype(np.int16).tobytes()


def _save_wav(path: str, stereo_pcm: bytes, fs: int = FS) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(fs)
        wf.writeframes(stereo_pcm)


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
    stereo = _to_stereo_float32(mono)
    _save_wav(str(path), _stereo_pcm_bytes(stereo))
    return str(path), stereo

