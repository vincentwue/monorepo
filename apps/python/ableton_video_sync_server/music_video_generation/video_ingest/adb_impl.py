from __future__ import annotations

import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

from .config import BERLIN, VIDEO_EXTS
from loguru import logger


# --- ADB core ---------------------------------------------------------------

def _adb(cmd: list[str], serial: Optional[str] = None) -> subprocess.CompletedProcess:
    base = ["adb"]
    if serial:
        base += ["-s", serial]
    full = base + cmd
    logger.debug("[adb] running: %s", " ".join(full))
    result = subprocess.run(full, check=True, capture_output=True, text=True)
    if result.stderr:
        logger.debug("[adb] stderr: %s", result.stderr.strip())
    return result

def _parse_ls_l_line(remote_dir: str, line: str) -> Optional[tuple[str, float, int]]:
    """Parse a toybox `ls -l` line into (path, mtime_epoch, size) if it's a video file.

    Works for lines like:
      -rwxrwx--- 1 u0_a271 media_rw 7265287 2025-10-03 17:35 VID_20251003_173528.mp4
    """
    ln = line.strip()
    if not ln or ln.startswith("total "):
        return None

    # Split into exactly 8 fields: perm, links, owner, group, size, date, time, name...
    parts = re.split(r"\s+", ln, maxsplit=7)
    if len(parts) < 8:
        return None

    _, _, _, _, size_s, date_s, time_s, name = parts

    try:
        size = int(size_s)
    except ValueError:
        return None

    # Parse date/time robustly (handles HH:MM or HH:MM:SS)
    dt_str = f"{date_s} {time_s}"
    try:
        # fromisoformat accepts both "YYYY-MM-DD HH:MM" and "YYYY-MM-DD HH:MM:SS"
        dt = datetime.fromisoformat(dt_str).replace(tzinfo=BERLIN)
    except ValueError:
        # Final fallback to strptime with two common formats
        dt = None
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
            try:
                dt = datetime.strptime(dt_str, fmt).replace(tzinfo=BERLIN)
                break
            except ValueError:
                continue
        if dt is None:
            return None

    mtime = dt.timestamp()
    path = f"{remote_dir.rstrip('/')}/{name}"

    if Path(path).suffix.lower() not in VIDEO_EXTS:
        return None

    return (path, mtime, size)

def _parse_stat_t_line(line: str) -> Optional[tuple[str, float, int]]:
    """Parse a toybox `stat -t` line into (path, mtime_epoch, size) heuristically."""
    ln = line.strip()
    if not ln:
        return None
    toks = ln.split()
    if len(toks) < 2:
        return None
    name = toks[-1]
    ints: list[int] = []
    for t in toks:
        try:
            iv = int(t)
            ints.append(iv)
        except ValueError:
            continue
    if not ints:
        return None
    size = next((iv for iv in ints if iv >= 0), None)
    if size is None:
        return None
    now = int(datetime.now(tz=BERLIN).timestamp())
    epochs = [iv for iv in ints if iv >= 1_000_000_000]
    if epochs:
        mtime = float(sorted(epochs, key=lambda v: abs(v - now))[0])
    else:
        mtime = float(max(ints))
    if Path(name).suffix.lower() not in VIDEO_EXTS:
        return None
    return (name, mtime, int(size))


# --- High-level ADB ops -----------------------------------------------------

def scan_adb(remote_dir: str, serial: Optional[str]) -> list[tuple[str, float, int]]:
    """Return list of (remote_path, mtime_epoch, size)."""
    remote = str(remote_dir).rstrip("/")
    logger.info("[ingest][adb] scanning %s (serial=%s)", remote, serial or "default")

    # Strategy A: ls -l (flat folder)
    try:
        cp1 = _adb(["shell", "toybox", "ls", "-l", remote], serial=serial)
        out1: list[tuple[str, float, int]] = []
        for ln in cp1.stdout.splitlines():
            parsed = _parse_ls_l_line(remote, ln)
            if parsed:
                out1.append(parsed)
        if out1:
            logger.info("[ingest][adb] ls -l returned %d candidate(s)", len(out1))
            return out1
    except Exception as exc:
        logger.warning("[ingest][adb] ls -l failed for %s: %s", remote, exc)
        pass

    # Strategy B: recursive find + stat -t
    try:
        shell_snippet = f"toybox find {remote} -type f -print0 | toybox xargs -0 -n1 toybox stat -t"
        cp2 = _adb(["shell", shell_snippet], serial=serial)
        out2: list[tuple[str, float, int]] = []
        for ln in cp2.stdout.splitlines():
            parsed = _parse_stat_t_line(ln)
            if parsed:
                out2.append((f"{remote}/{parsed[0]}", parsed[1], parsed[2]))
        return out2
    except Exception as exc:
        logger.error("[ingest][adb] recursive scan failed for %s: %s", remote, exc)
        return []


def adb_pull(remote_path: str, dest: Path, serial: Optional[str]) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["adb", *( ["-s", serial] if serial else [] ), "pull", remote_path, str(dest)], check=True)


__all__ = [
    "scan_adb",
    "adb_pull",
    "_parse_ls_l_line",
    "_parse_stat_t_line",
]
