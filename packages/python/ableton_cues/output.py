from __future__ import annotations

import json
import logging
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from .audio_output import AudioOutputSelector
from .player import CuePlayer

logger = logging.getLogger(__name__)

SETTINGS_PATH = Path(__file__).with_name("cue_output_settings.json")
ROOT_DIR = Path(__file__).resolve().parents[4]
EXAMPLE_CUE_PATH = (ROOT_DIR / "apps" / "python" / "ableton_video_sync_server" / "music_video_generation" / "ableton" / "cue_refs" / "start.wav").resolve()

DEFAULT_VOLUME = 1.0
MIN_VOLUME = 0.0
MAX_VOLUME = 2.5


@dataclass
class CueSpeakerSettings:
    device_index: Optional[int] = None
    volume: float = DEFAULT_VOLUME


class CueOutputService:
    """Manage cue speaker preferences and helper actions."""

    def __init__(
        self,
        settings_path: Path | str | None = None,
        example_cue_path: Path | str | None = None,
    ) -> None:
        self.settings_path = Path(settings_path) if settings_path else SETTINGS_PATH
        self.example_cue_path = Path(example_cue_path) if example_cue_path else EXAMPLE_CUE_PATH
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ helpers
    def _clamp_volume(self, value: float | int | None) -> float:
        if value is None:
            return DEFAULT_VOLUME
        numeric = float(value)
        return max(MIN_VOLUME, min(MAX_VOLUME, numeric))

    def load_settings(self) -> CueSpeakerSettings:
        if not self.settings_path.exists():
            return CueSpeakerSettings()
        try:
            data = json.loads(self.settings_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logger.warning("Cue speaker settings file is corrupted. Resetting to defaults.")
            return CueSpeakerSettings()
        return CueSpeakerSettings(
            device_index=data.get("device_index"),
            volume=self._clamp_volume(data.get("volume", DEFAULT_VOLUME)),
        )

    def save_settings(self, settings: CueSpeakerSettings) -> CueSpeakerSettings:
        payload = {
            "device_index": settings.device_index,
            "volume": self._clamp_volume(settings.volume),
        }
        tmp_path = self.settings_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp_path.replace(self.settings_path)
        return CueSpeakerSettings(**payload)

    def _create_selector(self) -> AudioOutputSelector:
        return AudioOutputSelector()

    def _list_outputs(self) -> Tuple[List[Dict], Optional[int], Optional[str]]:
        try:
            selector = self._create_selector()
            outputs = selector.list_outputs()
            recommended = selector.get_screen_output_index()
            if recommended is None:
                try:
                    recommended = selector.get_default_output_index()
                except Exception:
                    recommended = None
            return outputs, recommended, None
        except Exception as exc:
            message = (
                "Unable to enumerate audio outputs. Install the 'sounddevice' package or connect an audio device."
            )
            logger.warning("Cue output discovery failed: %s", exc)
            return [], None, message

    def _apply_player_settings(self, settings: CueSpeakerSettings) -> None:
        if CuePlayer is None:
            return
        try:
            cp = CuePlayer.instance()
            cp.master_gain = settings.volume
            if settings.device_index is not None:
                cp.device_index = settings.device_index
        except Exception as exc:
            logger.warning("Failed to apply cue speaker preferences: %s", exc)

    def apply_saved_preferences(self) -> CueSpeakerSettings:
        settings = self.load_settings()
        self._apply_player_settings(settings)
        return settings

    # ---------------------------------------------------------------- public API
    def describe(self) -> Dict:
        settings = self.load_settings()
        outputs, recommended, warning = self._list_outputs()
        valid_indexes = {device["index"] for device in outputs}
        selected_index = settings.device_index if settings.device_index in valid_indexes else None
        if selected_index is None and settings.device_index is not None:
            settings = self.save_settings(CueSpeakerSettings(device_index=None, volume=settings.volume))
        return {
            "outputs": outputs,
            "recommended_device_index": recommended,
            "selected_device_index": selected_index,
            "volume": settings.volume,
            "warning": warning,
        }

    def update_device(self, device_index: Optional[int]) -> Dict:
        settings = self.load_settings()
        if device_index is not None:
            outputs, _, _ = self._list_outputs()
            if not any(device["index"] == device_index for device in outputs):
                raise ValueError(f"Audio output {device_index} is not available.")
        next_settings = CueSpeakerSettings(device_index=device_index, volume=settings.volume)
        saved = self.save_settings(next_settings)
        self._apply_player_settings(saved)
        return self.describe()

    def update_volume(self, volume: float) -> Dict:
        settings = self.load_settings()
        saved = self.save_settings(CueSpeakerSettings(device_index=settings.device_index, volume=volume))
        self._apply_player_settings(saved)
        return self.describe()

    def play_example(self, device_index: Optional[int] = None, volume: Optional[float] = None) -> None:
        if CuePlayer is None:
            raise RuntimeError("Cue playback backend is not available.")
        stereo, samplerate = self._load_example_audio()
        stored = self.load_settings()
        target_volume = self._clamp_volume(volume if volume is not None else stored.volume)
        cp = CuePlayer.instance()
        previous_device = cp.device_index
        previous_gain = cp.master_gain
        try:
            if device_index is not None:
                cp.device_index = device_index
            elif stored.device_index is not None:
                cp.device_index = stored.device_index
            cp.master_gain = target_volume
            cp.play(stereo, samplerate=samplerate)
        finally:
            cp.master_gain = previous_gain
            cp.device_index = previous_device

    # -------------------------------------------------------------- audio utils
    def _load_example_audio(self) -> Tuple[np.ndarray, int]:
        if not self.example_cue_path.exists():
            raise FileNotFoundError(f"Example cue not found at {self.example_cue_path}")
        with wave.open(str(self.example_cue_path), "rb") as handle:
            frames = handle.readframes(handle.getnframes())
            sample_width = handle.getsampwidth()
            dtype, scale, offset = self._dtype_for_width(sample_width)
            raw = np.frombuffer(frames, dtype=dtype).astype(np.float32)
            if offset != 0.0:
                raw = (raw - offset) / scale
            else:
                raw = raw / scale
            channels = handle.getnchannels()
            if channels == 1:
                stereo = np.repeat(raw.reshape(-1, 1), 2, axis=1)
            else:
                stereo = raw.reshape(-1, channels)
                if channels > 2:
                    stereo = stereo[:, :2]
            return stereo, handle.getframerate()

    @staticmethod
    def _dtype_for_width(width: int) -> Tuple[np.dtype, float, float]:
        if width == 1:
            return np.uint8, 128.0, 128.0
        if width == 2:
            return np.int16, 32768.0, 0.0
        if width == 4:
            return np.int32, 2147483648.0, 0.0
        raise RuntimeError(f"Unsupported sample width: {width}")


__all__ = [
    "CueOutputService",
    "CueSpeakerSettings",
    "DEFAULT_VOLUME",
    "MIN_VOLUME",
    "MAX_VOLUME",
]
