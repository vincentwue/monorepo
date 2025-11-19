from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional

try:
    import sounddevice as sd  # type: ignore
except ImportError:
    sd = None  # type: ignore


@dataclass
class AudioDevice:
    name: str
    index: int


class AudioOutputSelector:
    SCREEN_KEYWORDS = [
        "hdmi",
        "display",
        "nvidia high definition",
        "intel display audio",
        "digital audio",
        "monitor",
        "tv",
    ]

    def __init__(self) -> None:
        if sd is None:
            raise RuntimeError("sounddevice is not available.")
        self.devices = sd.query_devices()
        try:
            self.hostapi_names = [api["name"].lower() for api in sd.query_hostapis()]
        except Exception:
            self.hostapi_names = []

    def list_outputs(self) -> List[Dict]:
        outputs: List[Dict] = []
        for idx, device in enumerate(self.devices):
            if device.get("max_output_channels", 0) <= 0:
                continue
            outputs.append(
                {
                    "index": idx,
                    "name": device.get("name", f"Device {idx}"),
                    "hostapi": self.hostapi_names[device.get("hostapi", 0)] if self.hostapi_names else "",
                    "channels": device.get("max_output_channels", 0),
                }
            )
        return outputs

    def get_default_output_index(self) -> Optional[int]:
        if sd is None:
            return None
        defaults = sd.default.device
        if not defaults or isinstance(defaults, int):
            return defaults if isinstance(defaults, int) else None
        return defaults[1]

    def get_screen_output_index(self) -> Optional[int]:
        pattern = re.compile("|".join(self.SCREEN_KEYWORDS), re.IGNORECASE)
        for device in self.list_outputs():
            if pattern.search(device.get("name", "")):
                return device.get("index")
        return None

    def auto_select_output(self) -> Optional[int]:
        screen_idx = self.get_screen_output_index()
        if screen_idx is not None:
            return screen_idx
        return self.get_default_output_index()


__all__ = ["AudioOutputSelector", "AudioDevice"]
