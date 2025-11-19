from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Sequence

from .config import BERLIN


# --- Core wrapper ------------------------------------------------------------
@dataclass(frozen=True)
class VideoSource:
    """
    A simple wrapper for a video source.

    Attributes
    ----------
    path: str | Path
        The path that is watched/scanned. For ADB, this is the remote path on the phone
        (e.g. "/sdcard/DCIM/OpenCamera"). For filesystem sources, it is a local path
        (e.g. an SD card drive letter or a mounted folder).
    device_name: str
        Human-friendly tag like "marco_phone", "vincent_phone", "lumix"  used to build
        output directories.
    kind: str
        One of {"filesystem", "adb"}. "filesystem" uses local filesystem APIs.
        "adb" shells into an Android device (requires `adb` in PATH); you must also
        set `adb_serial` if multiple phones are connected.
    adb_serial: Optional[str]
        If kind=="adb", optionally pin to a specific device serial (adb devices).
    """

    path: Path | str
    device_name: str
    kind: str = "filesystem"
    adb_serial: Optional[str] = None


# --- Persistent state ("memorize what we last scraped") ---------------------
class StateStore:
    """
    JSON-backed store mapping a unique source key to a cursor of what was last processed.

    We store per-source a dictionary:
        {
          "last_seen": "2025-10-03T15:04:05+02:00",  # ISO time when we last ran
          "last_items": {"/abs/or/remote/path/file.mp4": {"mtime": 1696348842.1, "size": 12345}}
        }

    For simplicity and speed, we keep only the latest processed item per source (by mtime),
    plus a small cache of the last N (to avoid duplicates if clocks wobble).
    """

    def __init__(self, path: Path, keep_last_n: int = 20) -> None:
        self.path = Path(path)
        self.keep_last_n = keep_last_n
        if not self.path.exists():
            self._data: dict[str, dict] = {}
        else:
            try:
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                self._data = {}

    def save(self) -> None:
        self.path.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")

    def mark_processed(self, source: VideoSource, items: Sequence[tuple[str, float, int]]) -> None:
        """
        items: sequence of (absolute_identifier, mtime, size)
        """
        key = self._key(source)
        d = self._data.setdefault(key, {"last_seen": None, "recent": []})
        now = datetime.now(tz=BERLIN).isoformat()
        d["last_seen"] = now
        recent = d.get("recent", [])
        for ident, mtime, size in items:
            recent.append({"id": ident, "mtime": mtime, "size": size})
        # Keep only latest N by mtime
        recent.sort(key=lambda x: x["mtime"])  # old->new
        d["recent"] = recent[-self.keep_last_n :]
        self._data[key] = d
        self.save()

    def was_seen(self, source: VideoSource, ident: str, mtime: float, size: int) -> bool:
        key = self._key(source)
        d = self._data.get(key)
        if not d:
            return False
        for r in d.get("recent", []):
            if r["id"] == ident and int(r["size"]) == int(size) and abs(float(r["mtime"]) - float(mtime)) < 1.0:
                return True
        return False

    @staticmethod
    def _key(source: VideoSource) -> str:
        return f"{source.kind}:{source.device_name}:{str(source.path)}"


__all__ = ["VideoSource", "StateStore"]
