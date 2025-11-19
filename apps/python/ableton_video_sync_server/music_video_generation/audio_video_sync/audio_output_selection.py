# audio_output_selection.py
from __future__ import annotations
import re
import platform
import numpy as np

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
            raise RuntimeError("sounddevice nicht installiert. Bitte 'pip install sounddevice' ausfhren.")
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
        print("\nVerfgbare Audio-Ausgnge:")
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
            print(f" Bildschirm-Audio erkannt  {self.devices[screen_idx]['name']}")
            return screen_idx
        default_idx = self.get_default_output_index()
        print(f" Kein Bildschirm-Audio erkannt, verwende Default  {self.devices[default_idx]['name']}")
        return default_idx


# ---------------- MAIN: Testton abspielen ----------------
if __name__ == "__main__":
    selector = AudioOutputSelector()
    selector.print_outputs()
    device_index = selector.auto_select_output()

    print(f"\n Testton auf Device {device_index} ({selector.devices[device_index]['name']}) ...")

    fs = 48000
    duration = 1.5  # Sekunden
    freq = 440.0    # A4-Ton
    t = np.linspace(0, duration, int(fs * duration), endpoint=False)
    wave = 0.2 * np.sin(2 * np.pi * freq * t)

    sd.play(wave, samplerate=fs, device=device_index)
    sd.wait()
    print("[OK] Test abgeschlossen.")
