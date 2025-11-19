from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Sequence

from playground.multi_video_generator.video_ingest.models import VideoSource, StateStore
from server.packages.music_video_generation.src.music_video_generation.ingest.ingest import ingest


sources = [
        VideoSource(path="/storage/emulated/0/DCIM/OpenCamera", device_name="marco_phone", kind="adb", adb_serial="53071FDAP002CS"),
        VideoSource(path="/storage/emulated/0/DCIM/OpenCamera", device_name="vincent_phone", kind="adb", adb_serial="2A101FDH2006TG"),
        VideoSource(path="F:/DCIM/106_PANA", device_name="lumix", kind="filesystem"),
    ]

def ingest_videos_main(song_name=None) -> int:
    song_name = song_name or "debug_project"
    base_out = Path(f"D:\\music_video_generation\\{song_name}\\footage\\videos")
    os.makedirs(base_out, exist_ok=True)
    # state_file: Path = Path.cwd() / "video_ingest_state.json"
    state_file: Path = base_out / "video_ingest_state.json"
    state = StateStore(path=state_file)
    copied = ingest(sources, base_out, state=state, only_today=False)
    print(f"Copied {len(copied)} files:")
    for p in copied:
        print("  ", p)
    return 0


if __name__ == "__main__":
    raise SystemExit(ingest_videos_main())
