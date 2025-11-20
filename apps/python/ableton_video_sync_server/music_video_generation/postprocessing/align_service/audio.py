from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional, List

from loguru import logger

AUDIO_EXTS = (".wav", ".mp3", ".m4a", ".aac", ".flac", ".aiff")


def resolve_audio(root: Path, override: Optional[str]) -> Path:
    """
    Pick the master audio:
    - explicit override, if provided
    - otherwise first audio file in footage/music
    - otherwise first audio file in project root
    """
    if override:
        audio = Path(override).expanduser().resolve()
        if not audio.exists():
            raise ValueError(f"Audio file not found: {override}")
        return audio

    music_dir = root / "footage" / "music"
    candidates: List[Path] = []

    if music_dir.exists():
        candidates.extend(
            sorted(p for p in music_dir.iterdir() if p.suffix.lower() in AUDIO_EXTS)
        )

    if not candidates:
        candidates.extend(
            sorted(p for p in root.glob("*") if p.is_file() and p.suffix.lower() in AUDIO_EXTS)
        )

    if not candidates:
        raise ValueError("No audio files found in project. Provide audio_path explicitly.")

    return candidates[0]


def probe_duration(path: Path) -> float:
    """
    Return media duration in seconds using ffprobe.
    """
    try:
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ]
        out = subprocess.check_output(cmd, text=True).strip()
        dur = float(out)
        if dur <= 0:
            raise RuntimeError(f"Non-positive duration for {path}")
        return dur
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"ffprobe failed for {path}: {exc}") from exc
    except ValueError as exc:
        raise RuntimeError(f"Unable to parse duration for {path}: {exc}") from exc
