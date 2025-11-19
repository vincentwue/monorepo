from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Optional

import numpy as np

from .constants import DEFAULT_FADE_MS, DEFAULT_PEAK_DB, DEFAULT_REF_DIR, DEFAULT_SAMPLE_RATE
from . import io, signals


@dataclass
class CueRender:
    name: str
    mono: np.ndarray
    stereo: np.ndarray
    path: Optional[Path] = None


class CueLibrary:
    def __init__(
        self,
        *,
        sample_rate: int = DEFAULT_SAMPLE_RATE,
        peak_db: float = DEFAULT_PEAK_DB,
    ) -> None:
        self.sample_rate = sample_rate
        self.peak_db = peak_db

    # --- primitive generation helpers -------------------------------------------------
    def start_cue(self) -> np.ndarray:
        return signals.start_cue(self.sample_rate)

    def end_cue(self) -> np.ndarray:
        return signals.end_cue(self.sample_rate)

    def stop_cue(self, total_dur: float = 1.2, seed: int | None = None) -> np.ndarray:
        return signals.stop_cue(total_dur=total_dur, seed=seed, fs=self.sample_rate)

    def unique_cue(self, seed: int, length: float = 1.3) -> np.ndarray:
        return signals.unique_cue(seed=seed, length=length, fs=self.sample_rate)

    def barker_bpsk(self, chip_ms: float = 18.0, carrier_hz: float = 3000.0) -> np.ndarray:
        return signals.barker_bpsk(chip_ms=chip_ms, carrier_hz=carrier_hz, fs=self.sample_rate)

    def fade(self, payload: np.ndarray, ms: int = DEFAULT_FADE_MS) -> np.ndarray:
        return signals.fade(payload, ms=ms, fs=self.sample_rate)

    # --- rendering helpers ------------------------------------------------------------
    def to_stereo(self, mono: np.ndarray) -> np.ndarray:
        return io.to_stereo(mono, peak_db=self.peak_db)

    def render(self, name: str, mono: np.ndarray) -> CueRender:
        stereo = self.to_stereo(mono)
        return CueRender(name=name, mono=mono, stereo=stereo, path=None)

    def save(self, render: CueRender, target: str | Path) -> CueRender:
        path = Path(target)
        io.save_wav(path, render.stereo, fs=self.sample_rate)
        render.path = path
        return render

    # --- higher level workflows -------------------------------------------------------
    def ensure_primary_references(
        self,
        target_dir: str | Path | None = None,
        *,
        names: Iterable[str] = ("start", "end"),
    ) -> Dict[str, Path]:
        target = Path(target_dir or DEFAULT_REF_DIR)
        target.mkdir(parents=True, exist_ok=True)
        outputs: Dict[str, Path] = {}
        for name in names:
            if name == "start":
                mono = self.start_cue()
            elif name == "end":
                mono = self.end_cue()
            else:
                raise ValueError(f"Unsupported primary cue name: {name}")
            render = self.render(name, mono)
            path = target / f"{name}.wav"
            self.save(render, path)
            outputs[name] = path
        return outputs

    def ensure_stop_reference(
        self,
        filename: str = "stop.wav",
        *,
        target_dir: str | Path | None = None,
        seed: int | None = None,
    ) -> Path:
        target = Path(target_dir or DEFAULT_REF_DIR)
        target.mkdir(parents=True, exist_ok=True)
        mono = self.stop_cue(seed=seed)
        render = self.render("stop", mono)
        path = target / filename
        self.save(render, path)
        return path


__all__ = ["CueLibrary", "CueRender"]
