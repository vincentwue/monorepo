import json
import subprocess
from typing import List, Tuple, Optional
import os
import shutil
import subprocess
import sys

# from playground.multi_video_generator.act import Act

def _open_with_vlc(filepath: str) -> bool:
    """Versucht VLC zu starten; gibt True zurck, wenns geklappt hat."""
    vlc = shutil.which("vlc")
    if not vlc:
        # Hufige Windows-Installationspfade
        candidates = [
            r"C:\Program Files\VideoLAN\VLC\vlc.exe",
            r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe",
        ]
        for c in candidates:
            if os.path.exists(c):
                vlc = c
                break

    if not vlc:
        return False

    try:
        creationflags = 0
        if os.name == "nt":
            # Fenster nicht blockieren
            creationflags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        subprocess.Popen(
            [vlc, filepath],  # optional: "--play-and-exit" fr Auto-Beenden
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )
        return True
    except Exception as e:
        print(f"VLC-Start fehlgeschlagen: {e}")
        return False

def run(cmd: List[str]) -> None:
    """Run a subprocess and fail loudly on error."""
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)


def ffprobe_json(path: str) -> dict:
    """Return full ffprobe JSON for a media file."""
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        path,
    ]
    out = subprocess.check_output(cmd)
    return json.loads(out)


def get_video_props(path: str) -> Tuple[float, Optional[str], Optional[float]]:
    """
    Returns (duration_sec, vcodec, fps) using ffprobe.
    """
    meta = ffprobe_json(path)
    duration = float(meta["format"].get("duration", 0.0))
    vcodec, fps = None, None
    for s in meta.get("streams", []):
        if s.get("codec_type") == "video":
            vcodec = s.get("codec_name")
            afr = s.get("avg_frame_rate") or s.get("r_frame_rate")
            if afr and afr != "0/0":
                num, den = afr.split("/")
                fps = float(num) / float(den)
            break
    return duration, vcodec, fps

