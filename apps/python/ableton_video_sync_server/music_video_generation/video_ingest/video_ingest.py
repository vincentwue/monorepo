from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, date
from pathlib import Path
from typing import Iterable, Iterator, Optional, Sequence

try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError  # py>=3.9
except Exception:  # pragma: no cover
    from backports.zoneinfo import ZoneInfo, ZoneInfoNotFoundError  # type: ignore
from datetime import timezone, timedelta

# --- Config -----------------------------------------------------------------
try:
    BERLIN = ZoneInfo("Europe/Berlin")
except ZoneInfoNotFoundError:  # pragma: no cover - fallback when tzdata missing
    BERLIN = timezone(offset=timedelta(hours=1), name="Europe/Berlin")
VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".avi", ".mts", ".mkv"}
STATE_FILE = Path.home() / ".video_ingest_state.json"


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

    def __init__(self, path: Path = STATE_FILE, keep_last_n: int = 20) -> None:
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


# --- Utilities ---------------------------------------------------------------

def is_video(p: Path) -> bool:
    return p.suffix.lower() in VIDEO_EXTS


def same_day(dt: datetime, day: date, tz: ZoneInfo = BERLIN) -> bool:
    local = dt.astimezone(tz)
    return local.date() == day


# --- Filesystem implementation ----------------------------------------------

def scan_filesystem(source: VideoSource) -> list[Path]:
    base = Path(source.path)
    if not base.exists():
        return []
    out: list[Path] = []
    # one-level scan (DCIM/OpenCamera rarely has subfolders, but include walk for safety)
    for root, _dirs, files in os.walk(base):
        for name in files:
            p = Path(root) / name
            if is_video(p):
                out.append(p)
    return out


# --- ADB implementation (for Android phones; avoids MTP limitations) --------
# We avoid GNU-specific flags and fragile host quoting. Everything runs on-device.


def _adb(cmd: list[str], serial: Optional[str] = None) -> subprocess.CompletedProcess:
    base = ["adb"]
    if serial:
        base += ["-s", serial]
    return subprocess.run(base + cmd, check=True, capture_output=True, text=True)


def _parse_ls_l_line(remote_dir: str, line: str) -> Optional[tuple[str, float, int]]:
    """Parse one toybox `ls -l` line into (path, mtime_epoch, size) if it's a video file.

    Expected toybox layout:
        PERM LINKS OWNER GROUP SIZE YYYY-MM-DD HH:MM NAME...
    but file names can contain spaces, so we join tokens from index 7 onward.
    """
    ln = line.strip()
    if not ln or ln.startswith("total "):
        return None

    toks = ln.split()
    # Need at least: perm, links, owner, group, size, date, time, name
    if len(toks) < 8:
        return None

    try:
        size = int(toks[4])
        dt_str = f"{toks[5]} {toks[6]}"
        # Try common formats (some ROMs include seconds)
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
            try:
                dt = datetime.strptime(dt_str, fmt).replace(tzinfo=BERLIN)
                break
            except ValueError:
                dt = None  # try next
        if dt is None:
            return None
        mtime = dt.timestamp()

        # Join the rest for filename (handles spaces in names)
        name = " ".join(toks[7:])
        path = f"{remote_dir.rstrip('/')}/{name}"
    except Exception:
        return None

    if Path(path).suffix.lower() not in VIDEO_EXTS:
        return None

    return (path, mtime, size)


def _parse_stat_t_line(line: str) -> Optional[tuple[str, float, int]]:
    """Parse a toybox `stat -t` line into (path, mtime_epoch, size) heuristically.

    toybox `stat -t` prints: MODE NLINK UID GID SIZE ATIME MTIME CTIME NAME  (common layout)
    But to be robust across builds, we:
      - take the last token as NAME
      - find all integer-like tokens; choose SIZE as the first integer >= 0
      - choose MTIME as the integer that looks like an epoch (>= 1_000_000_000)
        or, if multiple, the one closest to "now".
    """
    ln = line.strip()
    if not ln:
        return None
    toks = ln.split()
    if len(toks) < 2:
        return None
    name = toks[-1]
    # Collect integer-like tokens
    ints: list[int] = []
    for t in toks:
        try:
            # Some fields may be negative; guard but allow zero/positive
            iv = int(t)
            ints.append(iv)
        except ValueError:
            continue
    if not ints:
        return None
    # Heuristic: size is the first non-negative int
    size = next((iv for iv in ints if iv >= 0), None)
    if size is None:
        return None
    # Heuristic for mtime: pick an epoch-like value
    now = int(datetime.now(tz=BERLIN).timestamp())
    epochs = [iv for iv in ints if iv >= 1_000_000_000]
    if epochs:
        # choose the one closest to 'now'
        mtime = float(sorted(epochs, key=lambda v: abs(v - now))[0])
    else:
        # fallback: use the largest int as mtime
        mtime = float(max(ints))
    if Path(name).suffix.lower() not in VIDEO_EXTS:
        return None
    return (name, mtime, int(size))


def scan_adb(source: VideoSource) -> list[tuple[str, float, int]]:
    """
    Robust ADB scanner that avoids fragile quoting and MediaStore variations.

    Strategy A (preferred):
      `toybox ls -l <dir>` and parse size + timestamp (YYYY-MM-DD HH:MM). This is fast and
      matched your manual test.

    Strategy B: recursive `toybox find ... -print0 | toybox xargs -0 -n1 toybox stat -t` and
      parse using a heuristic.
    """
    assert source.kind == "adb"
    remote = str(source.path).rstrip("/")

    # --- Strategy A: ls -l (flat folder)  works on your device
    try:
        cp1 = _adb(["shell", "toybox", "ls", "-l", remote], serial=source.adb_serial)
        out1: list[tuple[str, float, int]] = []
        for ln in cp1.stdout.splitlines():
            parsed = _parse_ls_l_line(remote, ln)
            if parsed:
                out1.append(parsed)
        if out1:
            return out1
    except Exception:
        pass

    # --- Strategy B: recursive find + stat -t (handles subfolders)
    try:
        shell_snippet = (
            f"toybox find {remote} -type f -print0 | toybox xargs -0 -n1 toybox stat -t"
        )
        cp2 = _adb(["shell", shell_snippet], serial=source.adb_serial)
        out2: list[tuple[str, float, int]] = []
        for ln in cp2.stdout.splitlines():
            parsed = _parse_stat_t_line(ln)
            if parsed:
                out2.append(parsed)
        return out2
    except Exception:
        return []


def adb_pull(remote_path: str, dest: Path, serial: Optional[str]) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["adb", *( ["-s", serial] if serial else [] ), "pull", remote_path, str(dest)], check=True)



# --- Orchestration -----------------------------------------------------------

def ingest(
    sources: Sequence[VideoSource],
    base_output_dir: Path,
    state: Optional[StateStore] = None,
    only_today: bool = True,
) -> list[Path]:
    """
    Collect new, same-day videos from all sources, copying them into
    base_output_dir/<device_name>/YYYY-MM-DD/ .

    Returns list of output file paths that were copied.
    """
    state = state or StateStore()
    today = datetime.now(tz=BERLIN).date()
    copied: list[Path] = []

    for src in sources:
        if src.kind == "filesystem":
            files = scan_filesystem(src)
            # Convert to (id, mtime, size)
            entries: list[tuple[str, float, int, Path]] = []
            for p in files:
                try:
                    st = p.stat()
                except FileNotFoundError:
                    continue
                mtime = st.st_mtime
                size = st.st_size
                if only_today:
                    if not same_day(datetime.fromtimestamp(mtime, tz=BERLIN), today):
                        continue
                ident = str(p.resolve())
                entries.append((ident, mtime, size, p))

            # Filter unseen
            unseen = [(i, m, s, p) for (i, m, s, p) in entries if not state.was_seen(src, i, m, s)]
            # Sort newest first to copy in temporal order
            unseen.sort(key=lambda t: t[1])

            # Copy
            for ident, mtime, size, p in unseen:
                day_str = datetime.fromtimestamp(mtime, tz=BERLIN).strftime("%Y-%m-%d")
                out_dir = base_output_dir / src.device_name / day_str
                out_dir.mkdir(parents=True, exist_ok=True)
                dest = out_dir / p.name
                # If destination exists with same size, skip
                if dest.exists() and dest.stat().st_size == size:
                    pass
                else:
                    shutil.copy2(p, dest)
                copied.append(dest)
            # Record in state
            state.mark_processed(src, [(i, m, s) for (i, m, s, _p) in unseen])

        elif src.kind == "adb":
            entries_adb = scan_adb(src)  # (remote, mtime, size)
            if only_today:
                entries_adb = [e for e in entries_adb if same_day(datetime.fromtimestamp(e[1], tz=BERLIN), today)]
            unseen = [e for e in entries_adb if not state.was_seen(src, e[0], e[1], e[2])]
            unseen.sort(key=lambda e: e[1])  # by mtime
            for remote, mtime, size in unseen:
                day_str = datetime.fromtimestamp(mtime, tz=BERLIN).strftime("%Y-%m-%d")
                out_dir = base_output_dir / src.device_name / day_str
                dest = out_dir / Path(remote).name
                adb_pull(remote, dest, src.adb_serial)
                copied.append(dest)
            state.mark_processed(src, unseen)

        else:
            raise ValueError(f"Unknown source kind: {src.kind}")

    return copied


# --- Light-weight watching strategies ---------------------------------------
"""
Practical, resource-saving watching when 2 phones + 1 SD card are connected:

1) SD card (drive letter / local filesystem):
   - Use watchdog (Observer on Windows) which leverages ReadDirectoryChangesW.
     It is event-driven and very light. Fall back to periodic scan if you prefer no deps.

2) Phones over MTP (those Explorer paths like \\\\:\\Pixel 9 Pro\\Internal shared storage\\...):
   - Windows MTP virtual folders are *not* real NT paths; file watching APIs and even
     Python's os.listdir/stat usually don't work. The most reliable automation is ADB.
   - Recommendation: enable Developer Options + USB Debugging, then use `kind="adb"`
     with path "/sdcard/DCIM/OpenCamera". This avoids polling Explorer's MTP layer.
   - If you must stick to MTP: polling via Shell COM APIs is possible but complex/fragile.
     Prefer ADB-based polling every 1030s; it is inexpensive (~milliseconds per scan).

Minimal CPU approach:
   - Run one asyncio loop with per-source intervals (e.g., SD card via watchdog events,
     phones via adb scan every 15s). Debounce copy until files stop growing (check size twice).
"""


# --- Helper: build ADB sources from a serialname map -----------------------

def make_adb_sources(serial_to_name: dict[str, str], camera_path: str) -> list[VideoSource]:
    sources: list[VideoSource] = []
    for serial, name in serial_to_name.items():
        sources.append(
            VideoSource(
                path=camera_path,
                device_name=name,
                kind="adb",
                adb_serial=serial,
            )
        )
    return sources


# --- Example CLI -------------------------------------------------------------

def _parse_args(argv: Sequence[str]) -> tuple[list[VideoSource], Path]:
    """Return sources in the original, simple list structure.

    - Phones via ADB with fixed serials
    - Lumix (or any SD card) as a plain filesystem path
    """
    sources = [
        VideoSource(path="/storage/emulated/0/DCIM/OpenCamera", device_name="marco_phone", kind="adb", adb_serial="53071FDAP002CS"),
        VideoSource(path="/storage/emulated/0/DCIM/OpenCamera", device_name="vincent_phone", kind="adb", adb_serial="2A101FDH2006TG"),
        VideoSource(path=r"D:\DCIM\100PANA", device_name="lumix", kind="filesystem"),
    ]
    base_out = Path.cwd() / "video_ingest_out"
    return sources, base_out


def main(argv: Sequence[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    sources, base_out = _parse_args(argv)
    state = StateStore()
    copied = ingest(sources, base_out, state=state, only_today=True)
    print(f"Copied {len(copied)} files:")
    for p in copied:
        print("  ", p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
