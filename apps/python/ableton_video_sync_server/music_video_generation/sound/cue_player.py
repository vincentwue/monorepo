# Copied and organized from playground.multi_video_generator.sync.cue_player
from __future__ import annotations
import os, sys, time, wave, ctypes, platform
import numpy as np
from typing import Optional
from dataclasses import dataclass
import threading

FS = 48000
PEAK = 10 ** (-1.0 / 20)
FADE_MS = 8
REF_DIR = "cue_refs"

IS_WINDOWS = platform.system() == "Windows"
_user32 = ctypes.windll.user32 if IS_WINDOWS else None
BACKEND_ENV = os.environ.get("CUE_BACKEND", "").lower().strip() or None


def fade(x: np.ndarray, ms=FADE_MS, fs=FS):
    n = max(1, int(ms * fs / 1000))
    r = np.linspace(0, 1, n, dtype=np.float32)
    x[:n] *= r
    x[-n:] *= r[::-1]
    return x


def to_stereo(x: np.ndarray) -> np.ndarray:
    y = np.clip(x * PEAK, -1, 1).astype(np.float32)
    return np.column_stack((y, y))


def stereo_to_pcm(stereo: np.ndarray) -> bytes:
    return (np.clip(stereo, -1, 1) * 32767).astype(np.int16).tobytes()


def unique_cue(seed: int, length=1.3, fs=FS) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n_total = int(length * fs)
    t = np.linspace(0, length, n_total, endpoint=False, dtype=np.float32)
    blues = np.array([220.0, 261.63, 293.66, 311.13, 329.63, 392.0])
    note_pool = np.concatenate([blues, blues * 2, blues * 0.5])
    tone = np.zeros_like(t)
    num_notes = rng.integers(3, 6)
    note_starts = np.sort(rng.choice(np.linspace(0, length - 0.2, 20), num_notes, replace=False))
    note_durs = rng.uniform(0.05, 0.25, size=num_notes)
    for i in range(num_notes):
        start_t = note_starts[i]
        dur = note_durs[i]
        f = rng.choice(note_pool) * rng.uniform(0.9, 1.1)
        note_t = np.linspace(0, dur, int(fs * dur), endpoint=False)
        w = np.sin(2 * np.pi * f * note_t) * (0.5 + 0.5 * np.sin(2 * np.pi * rng.uniform(2, 5) * note_t))
        w += 0.3 * np.sin(2 * np.pi * 2 * f * note_t)
        w = fade(w, ms=FADE_MS, fs=fs)
        if rng.random() < 0.4:
            w[: int(0.01 * fs)] += rng.standard_normal(int(0.01 * fs)) * 0.1
        start_idx = int(start_t * fs)
        end_idx = min(start_idx + len(w), n_total)
        tone[start_idx:end_idx] += w[: end_idx - start_idx]
    tone = fade(tone, ms=FADE_MS * 2)
    tone /= np.max(np.abs(tone) + 1e-6)
    if rng.random() < 0.5:
        tone = np.convolve(tone, np.hanning(64) / 64, mode="same")
    else:
        smooth = np.convolve(tone, np.hanning(64) / 64, mode="same")
        tone -= smooth * 0.2
    return tone.astype(np.float32)


def mk_barker_bpsk(chip_ms: float = 18.0, carrier_hz: float = 3000.0, fs: int = FS) -> np.ndarray:
    barker = np.array([+1, +1, +1, +1, +1, -1, -1, +1, +1, -1, +1, -1, +1], dtype=np.float32)
    chip_n = max(1, int(round(fs * (chip_ms / 1000.0))))
    t_chip = np.linspace(0.0, chip_ms / 1000.0, chip_n, endpoint=False, dtype=np.float32)
    carrier = np.sin(2 * np.pi * carrier_hz * t_chip).astype(np.float32)
    parts = [(bit * carrier) for bit in barker]
    x = np.concatenate(parts).astype(np.float32)
    x = fade(x, ms=FADE_MS)
    peak = float(np.max(np.abs(x)) + 1e-6)
    x = (x / peak).astype(np.float32)
    return x


@dataclass
class CuePlayer:
    device_index: Optional[int] = None
    backend_name: str = "auto"
    master_gain: float = 1.0
    _instance: "CuePlayer" = None

    sd = None
    sa = None
    winsound = None
    fs_out = FS

    @classmethod
    def instance(cls) -> "CuePlayer":
        if cls._instance is None:
            cls._instance = CuePlayer()
            cls._instance._init_backend()
        return cls._instance

    def _init_backend(self):
        order = ([BACKEND_ENV] if BACKEND_ENV in {"winsound", "simpleaudio", "sounddevice"}
                 else ["sounddevice", "simpleaudio", "winsound"])
        for name in order:
            try:
                if name == "sounddevice":
                    import sounddevice as _sd
                    self.sd = _sd
                    self.backend_name = "sounddevice"
                    return
                elif name == "simpleaudio":
                    import simpleaudio as _sa
                    self.sa = _sa
                    self.backend_name = "simpleaudio"
                    return
                elif name == "winsound" and IS_WINDOWS:
                    import winsound as _ws
                    self.winsound = _ws
                    self.backend_name = "winsound"
                    return
            except Exception:
                continue
        raise RuntimeError("No usable audio backend found (sounddevice/simpleaudio/winsound)")

    def play(self, stereo: np.ndarray, samplerate=FS):
        payload = np.asarray(stereo, dtype=np.float32)
        if self.master_gain != 1.0:
            payload = np.clip(payload * float(self.master_gain), -1.0, 1.0)
        if self.backend_name == "sounddevice":
            self.sd.play(payload, samplerate=samplerate, blocking=True, device=self.device_index)
        elif self.backend_name == "simpleaudio":
            pcm = stereo_to_pcm(payload)
            self.sa.WaveObject(pcm, num_channels=2, bytes_per_sample=2, sample_rate=samplerate).play().wait_done()
        elif self.backend_name == "winsound":
            pcm = stereo_to_pcm(payload)
            tmp = os.path.join(REF_DIR, f"_tmp_{time.time_ns()}.wav")
            os.makedirs(REF_DIR, exist_ok=True)
            with wave.open(tmp, "wb") as wf:
                wf.setnchannels(2)
                wf.setsampwidth(2)
                wf.setframerate(samplerate)
                wf.writeframes(pcm)
            self.winsound.PlaySound(tmp, self.winsound.SND_FILENAME)
        else:
            raise RuntimeError("No valid backend loaded.")

    def play_seed(self, seed: int, dur=0.5, blocking=False, gain: float = 1.0):
        def _job():
            mono = unique_cue(seed, length=dur)
            stereo = to_stereo(mono)
            if gain != 1.0:
                stereo = np.clip(stereo * float(gain), -1.0, 1.0)
            self.play(stereo)
        if blocking:
            _job()
        else:
            threading.Thread(target=_job, daemon=True).start()

    def play_barker(self, chip_ms: float = 18.0, carrier_hz: float = 3000.0, gain: float = 1.0, blocking: bool = True):
        def _job():
            mono = mk_barker_bpsk(chip_ms=chip_ms, carrier_hz=carrier_hz, fs=self.fs_out)
            stereo = to_stereo(mono)
            if gain != 1.0:
                stereo = np.clip(stereo * float(gain), -1.0, 1.0)
            self.play(stereo, samplerate=self.fs_out)
        if blocking:
            _job()
        else:
            threading.Thread(target=_job, daemon=True).start()

