# Copied from playground.sync.sync_sound_generation.generate_audio_trigger_legacy
from __future__ import annotations
import os, wave
from pathlib import Path
import numpy as np

FS = 48000
PEAK = 10 ** (-0 / 20)
FADE_MS = 6
REF_DIR = "cue_refs"
START_NAME = "start"
END_NAME = "end"


def fade(x, ms=FADE_MS, fs=FS):
    n = max(1, int(ms * fs / 1000))
    r = np.linspace(0, 1, n, dtype=np.float32)
    x[:n] *= r
    x[-n:] *= r[::-1]
    return x


def tone(freq, dur):
    t = np.linspace(0, dur, int(FS * dur), endpoint=False, dtype=np.float32)
    return np.sin(2 * np.pi * freq * t)


def chirp_up(f0, f1, dur):
    t = np.linspace(0, dur, int(FS * dur), endpoint=False, dtype=np.float32)
    k = np.log(f1 / f0) / dur
    phase = 2 * np.pi * f0 * (np.expm1(k * t) / k)
    return np.sin(phase)


def mk_cue():
    x = np.concatenate([
        tone(800, 0.08),
        np.zeros(int(0.04 * FS), np.float32),
        tone(1600, 0.08),
        np.zeros(int(0.08 * FS), np.float32),
        chirp_up(600, 5000, 0.22),
    ])
    return fade(x)


def mk_start():
    return mk_cue()


def mk_end():
    return mk_cue()


def to_stereo_float32(mono: np.ndarray) -> np.ndarray:
    y = np.clip(mono * PEAK, -1, 1).astype(np.float32)
    return np.column_stack((y, y))


def stereo_pcm_bytes_from_float32(stereo_f32: np.ndarray) -> bytes:
    pcm16 = (np.clip(stereo_f32, -1, 1) * 32767).astype(np.int16)
    return pcm16.tobytes()


def save_wav(path, pcm_bytes: bytes):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(FS)
        wf.writeframes(pcm_bytes)


def ensure_refs(ref_dir: str | os.PathLike[str] | None = None):
    target_dir = Path(ref_dir) if ref_dir else Path(REF_DIR)
    target_dir.mkdir(parents=True, exist_ok=True)
    start_f32 = to_stereo_float32(mk_start())
    end_f32 = to_stereo_float32(mk_end())
    start_pcm = stereo_pcm_bytes_from_float32(start_f32)
    end_pcm = stereo_pcm_bytes_from_float32(end_f32)
    start_path = target_dir / f"{START_NAME}.wav"
    end_path = target_dir / f"{END_NAME}.wav"
    save_wav(str(start_path), start_pcm)
    save_wav(str(end_path), end_pcm)
    return str(start_path), str(end_path), start_f32, end_f32, start_pcm, end_pcm

