from __future__ import annotations

from datetime import datetime, date
from pathlib import Path

from .config import BERLIN, VIDEO_EXTS


def is_video(p: Path) -> bool:
    return p.suffix.lower() in VIDEO_EXTS


def same_day(dt: datetime, day: date) -> bool:
    local = dt.astimezone(BERLIN)
    return local.date() == day


__all__ = ["is_video", "same_day"]
