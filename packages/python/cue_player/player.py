from __future__ import annotations

import ctypes
import os
import platform
import threading
import time
import wave
from dataclasses import dataclass
from typing import Optional

import numpy as np

try:
    from cue_library import (
        DEFAULT_REF_DIR,
        DEFAULT_SAMPLE_RATE,
        barker_bpsk as mk_barker_bpsk,
        fade,
        to_stereo,
        unique_cue,
    )
    from cue_library.io import stereo_to_pcm
except ImportError:  # pragma: no cover - workspace fallback
    from packages.python.cue_library import (
        DEFAULT_REF_DIR,
        DEFAULT_SAMPLE_RATE,
        barker_bpsk as mk_barker_bpsk,
        fade,
        to_stereo,
        unique_cue,
    )
    from packages.python.cue_library.io import stereo_to_pcm

FS = DEFAULT_SAMPLE_RATE
REF_DIR = DEFAULT_REF_DIR

IS_WINDOWS = platform.system() == "Windows"
_user32 = ctypes.windll.user32 if IS_WINDOWS else None
BACKEND_ENV = os.environ.get("CUE_BACKEND", "").lower().strip() or None


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

    def _init_backend(self) -> None:
        order = (
            [BACKEND_ENV]
            if BACKEND_ENV in {"winsound", "simpleaudio", "sounddevice"}
            else ["sounddevice", "simpleaudio", "winsound"]
        )
        for name in order:
            try:
                if name == "sounddevice":
                    import sounddevice as _sd

                    self.sd = _sd
                    self.backend_name = "sounddevice"
                    return
                if name == "simpleaudio":
                    import simpleaudio as _sa

                    self.sa = _sa
                    self.backend_name = "simpleaudio"
                    return
                if name == "winsound" and IS_WINDOWS:
                    import winsound as _ws

                    self.winsound = _ws
                    self.backend_name = "winsound"
                    return
            except Exception:
                continue
        raise RuntimeError("No usable audio backend found (sounddevice/simpleaudio/winsound)")

    def play(self, stereo: np.ndarray, samplerate: int = FS) -> None:
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

    def play_seed(self, seed: int, dur: float = 0.5, blocking: bool = False, gain: float = 1.0) -> None:
        def _job() -> None:
            mono = unique_cue(seed, length=dur)
            stereo = to_stereo(mono)
            if gain != 1.0:
                stereo = np.clip(stereo * float(gain), -1.0, 1.0)
            self.play(stereo)

        if blocking:
            _job()
        else:
            threading.Thread(target=_job, daemon=True).start()

    def play_barker(
        self,
        chip_ms: float = 18.0,
        carrier_hz: float = 3000.0,
        gain: float = 1.0,
        blocking: bool = True,
    ) -> None:
        def _job() -> None:
            mono = mk_barker_bpsk(chip_ms=chip_ms, carrier_hz=carrier_hz, fs=self.fs_out)
            stereo = to_stereo(mono)
            if gain != 1.0:
                stereo = np.clip(stereo * float(gain), -1.0, 1.0)
            self.play(stereo, samplerate=self.fs_out)

        if blocking:
            _job()
        else:
            threading.Thread(target=_job, daemon=True).start()


__all__ = ["CuePlayer", "unique_cue", "mk_barker_bpsk", "to_stereo", "fade", "FS"]
