from __future__ import annotations

import json
from pathlib import Path
from typing import Final

try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError  # py>=3.9
except Exception:  # pragma: no cover
    from backports.zoneinfo import ZoneInfo, ZoneInfoNotFoundError  # type: ignore
from datetime import timezone, timedelta

# --- Timezone ---------------------------------------------------------------
try:
    BERLIN: Final = ZoneInfo("Europe/Berlin")
except ZoneInfoNotFoundError:  # pragma: no cover - fallback when tzdata missing
    BERLIN = timezone(offset=timedelta(hours=1), name="Europe/Berlin")


# --- File types -------------------------------------------------------------
VIDEO_EXTS: Final = {".mp4", ".mov", ".m4v", ".avi", ".mts", ".mkv"}

# --- Persistent state file --------------------------------------------------

__all__ = [
    "BERLIN",
    "VIDEO_EXTS",
]
