# Copied from playground.multi_video_generator.sync.audio_output_selection
from __future__ import annotations
import re

try:
    import sounddevice as sd
except ImportError:
    sd = None


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

    def __init__(self):
        if sd is None:
            raise RuntimeError("sounddevice not installed. Please `pip install sounddevice`.")
        self.devices = sd.query_devices()
        self.hostapi_names = [api["name"].lower() for api in sd.query_hostapis()]

    def list_outputs(self) -> list[dict]:
        outputs = []
        for idx, dev in enumerate(self.devices):
            if dev["max_output_channels"] > 0:
                outputs.append({
                    "index": idx,
                    "name": dev["name"],
                    "hostapi": self.hostapi_names[dev["hostapi"]],
                    "channels": dev["max_output_channels"],
                })
        return outputs

    def print_outputs(self) -> None:
        print("\nAvailable audio outputs:")
        for o in self.list_outputs():
            print(f"[{o['index']:2d}] {o['name']}  ({o['channels']}ch)  via {o['hostapi']}")

    def find_screen_output(self) -> dict | None:
        pattern = re.compile("|".join(self.SCREEN_KEYWORDS), re.IGNORECASE)
        for o in self.list_outputs():
            if pattern.search(o["name"]):
                return o
        return None

    def get_screen_output_index(self) -> int | None:
        out = self.find_screen_output()
        return out["index"] if out else None

    def get_default_output_index(self) -> int:
        default = sd.default.device
        if isinstance(default, (list, tuple)):
            return default[1]  # [input, output]
        return default

    def auto_select_output(self) -> int:
        screen_idx = self.get_screen_output_index()
        if screen_idx is not None:
            print(f"Detected screen audio -> {self.devices[screen_idx]['name']}")
            return screen_idx
        default_idx = self.get_default_output_index()
        print(f"No screen audio detected, using default -> {self.devices[default_idx]['name']}")
        return default_idx

