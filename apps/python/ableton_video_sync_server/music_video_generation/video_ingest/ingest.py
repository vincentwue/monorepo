from __future__ import annotations

import shutil
from loguru import logger
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, Sequence, Dict, Tuple, List

from .config import BERLIN
from .fs_impl import scan_filesystem
from .adb_impl import scan_adb, adb_pull
from .models import VideoSource, StateStore
from .utils import same_day



def ingest(
    sources: Sequence[VideoSource],
    base_output_dir: Path,
    state: Optional[StateStore] = None,
    only_today: bool = True,
    stop_event: Optional[threading.Event] = None,
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
        if stop_event and stop_event.is_set():
            logger.info("[ingest] stop requested before scanning %s; halting.", src.device_name)
            break
        logger.info("[ingest] Scanning source kind=%s name=%s path=%s", src.kind, src.device_name, src.path)
        if src.kind == "filesystem":
            files = scan_filesystem(src.path)
            entries: list[tuple[str, float, int, Path]] = []
            for p in files:
                try:
                    st = Path(p).stat()
                except FileNotFoundError:
                    continue
                mtime = st.st_mtime
                size = st.st_size
                if only_today and not same_day(datetime.fromtimestamp(mtime, tz=BERLIN), today):
                    logger.debug("[ingest] Skipping %s (not from today).", p)
                    continue
                ident = str(Path(p).resolve())
                entries.append((ident, mtime, size, Path(p)))

            unseen = [(i, m, s, p) for (i, m, s, p) in entries if not state.was_seen(src, i, m, s)]
            unseen.sort(key=lambda t: t[1])  # by mtime
            logger.info(
                "[ingest] Filesystem source %s yielded %d files (%d new).",
                src.device_name,
                len(entries),
                len(unseen),
            )

            for ident, mtime, size, p in unseen:
                if stop_event and stop_event.is_set():
                    logger.info("[ingest] stop requested; aborting filesystem copy loop.")
                    break
                out_dir = base_output_dir / src.device_name
                out_dir.mkdir(parents=True, exist_ok=True)
                dest = out_dir / p.name
                if dest.exists() and dest.stat().st_size == size:
                    logger.debug("[ingest] Skipping copy for %s (already up to date).", dest)
                else:
                    logger.info("[ingest] Copying %s -> %s", p, dest)
                    shutil.copy2(p, dest)
                copied.append(dest)
            state.mark_processed(src, [(i, m, s) for (i, m, s, _p) in unseen])

        elif src.kind == "adb":
            entries_adb = scan_adb(str(src.path), src.adb_serial)  # (remote, mtime, size)
            if only_today:
                entries_adb = [e for e in entries_adb if same_day(datetime.fromtimestamp(e[1], tz=BERLIN), today)]
            unseen = [e for e in entries_adb if not state.was_seen(src, e[0], e[1], e[2])]
            unseen.sort(key=lambda e: e[1])
            logger.info(
                "[ingest] ADB source %s yielded %d files (%d new).",
                src.device_name,
                len(entries_adb),
                len(unseen),
            )
            for remote, mtime, size in unseen:
                if stop_event and stop_event.is_set():
                    logger.info("[ingest] stop requested; aborting adb pull loop.")
                    break
                out_dir = base_output_dir / src.device_name
                dest = out_dir / Path(remote).name
                logger.info("[ingest] Pulling %s -> %s", remote, dest)
                adb_pull(remote, dest, src.adb_serial)
                copied.append(dest)
            state.mark_processed(src, unseen)

        else:
            raise ValueError(f"Unknown source kind: {src.kind}")

    return copied


def preview_ingest_counts(
    sources: Sequence[VideoSource],
    state: Optional[StateStore] = None,
    only_today: bool = True,
) -> Dict[str, Dict[str, int]]:
    """
    Analyze sources and return a mapping from device_name to total/new counts without copying.
    """
    state = state or StateStore()
    today = datetime.now(tz=BERLIN).date()
    summary: Dict[str, Dict[str, int]] = {}

    for src in sources:
        total = 0
        new = 0
        if src.kind == "filesystem":
            files = scan_filesystem(src.path)
            entries = []
            for p in files:
                try:
                    st = Path(p).stat()
                except FileNotFoundError:
                    continue
                mtime = st.st_mtime
                size = st.st_size
                if only_today and not same_day(datetime.fromtimestamp(mtime, tz=BERLIN), today):
                    continue
                ident = str(Path(p).resolve())
                entries.append((ident, mtime, size))
            total = len(entries)
            new = sum(1 for entry in entries if not state.was_seen(src, entry[0], entry[1], entry[2]))
        elif src.kind == "adb":
            entries_adb = scan_adb(str(src.path), src.adb_serial)
            if only_today:
                entries_adb = [
                    e for e in entries_adb if same_day(datetime.fromtimestamp(e[1], tz=BERLIN), today)
                ]
            total = len(entries_adb)
            new = sum(1 for entry in entries_adb if not state.was_seen(src, entry[0], entry[1], entry[2]))
        else:
            continue

        summary[src.device_name] = {"total": total, "new": new}

    return summary


__all__ = ["ingest", "preview_ingest_counts"]
