#!/usr/bin/env python3
"""
Sync-Cuts Video Generator (Tempo-Aware)
---------------------------------------
Renders a synchronized multi-camera video based on Ableton
recording cues and tempo (BPM). Cuts switch automatically
every N bars, aligned to the project tempo.

Workflow:
1. Reads Ableton recording (project metadata)
2. Finds all postprocessing video docs with matching start cue
3. Aligns their start times to the master Ableton timeline (t=0)
4. Generates a tempo-based cut sequence
"""

import os
import math
import random
from datetime import datetime
from pathlib import Path
from typing import List
from pymongo import MongoClient

from .ffmpeg_render import FFmpegRenderer
from .cut import CutClip


# === CONFIG ===
MONGO_URI = "mongodb://localhost:27025"
DB_NAME = "vincent_core"
COLL_REC = "ableton.recordings"
COLL_PP = "ableton.postprocessing"
OUTPUT_DIR = Path("D:/git_repos/todos/builds/sync_cuts")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

BAR_GROUP = 4                   # bars per cut (1, 2, 4, 8...)
CUT_LENGTH_S = None             # seconds override; None -> computed from BPM
CUSTOM_DURATION_S = 0.0         # 0 -> full song
DEBUG = True


# ==============================================================
# === Helpers ===
# ==============================================================

def get_audio_duration(audio_path: Path) -> float:
    """Safe audio duration (mutagen or ffprobe)."""
    try:
        from mutagen import File
        a = File(audio_path)
        if a and hasattr(a, "info"):
            dur = getattr(a.info, "length", 0.0)
            if dur and dur > 0:
                return float(dur)
    except Exception:
        pass

    try:
        import subprocess, json
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json", str(audio_path)
        ]
        out = subprocess.check_output(cmd)
        info = json.loads(out)
        return float(info["format"]["duration"])
    except Exception as e:
        print(f"[warn] Could not get audio duration: {e}")
        return 0.0


def get_ableton_recording(client: MongoClient, project_name: str):
    db = client[DB_NAME]
    rec = db[COLL_REC].find_one({
        "fields.ableton_recording.project_name": project_name
    })
    if not rec:
        raise RuntimeError(f"No ableton.recording found for project {project_name}")
    return rec


def find_videos_by_cue(client: MongoClient, start_cue: str):
    """Find all postprocessing videos referencing the same start cue."""
    db = client[DB_NAME]
    coll = db[COLL_PP]
    cur = coll.find({
        "$or": [
            {"fields.ableton_postprocessing.cue_refs_used": start_cue},
            {"fields.ableton_postprocessing.cue_ref_id": start_cue}
        ]
    })
    videos = list(cur)
    print(f"[info] Found {len(videos)} postprocessed videos with cue {start_cue}")
    return videos


def make_dummy_video(filename: str):
    from dataclasses import dataclass
    @dataclass
    class DummyVideo:
        filename: str
    return DummyVideo(filename)


# ==============================================================
# === Build synchronized cut sequence
# ==============================================================

def build_sync_sequence(videos: List[dict], song_duration: float, cut_len_s: float) -> List[CutClip]:
    """
    Given postprocessing video docs, create CutClips aligned to song time.
    Each video's start cue offset is used to align it globally.
    Then we alternate videos every N seconds (tempo-based).
    """
    seq: List[CutClip] = []
    if not videos:
        raise RuntimeError("No postprocessing videos provided.")

    # Flatten and align
    aligned = []
    for v in videos:
        f = v["fields"]["ableton_postprocessing"]
        path = f.get("file_path")
        if not path or not os.path.exists(path):
            continue
        segs = f.get("segments", [])
        start_offset = segs[0]["start_time_s"] if segs else 0.0
        aligned.append((path, start_offset))

    aligned.sort(key=lambda x: x[1])
    if not aligned:
        raise RuntimeError("No usable video files after alignment.")

    total_cuts = max(1, math.ceil(song_duration / cut_len_s))
    for i in range(total_cuts):
        start_t = i * cut_len_s
        end_t = min(song_duration, start_t + cut_len_s)
        seg_duration = end_t - start_t

        vid_path, vid_offset = aligned[i % len(aligned)]
        seq.append(CutClip(
            video=make_dummy_video(vid_path),
            inpoint=vid_offset + start_t,
            outpoint=vid_offset + start_t + seg_duration,
            duration=seg_duration,
            time_global=start_t,
        ))

    print(f"[debug] Built {len(seq)} tempo-synced cuts for {song_duration:.1f}s")
    return seq


# ==============================================================
# === Main entry
# ==============================================================

def render_sync_video(
    project_name: str,
    audio_path: Path,
    *,
    bars_per_cut: int | None = None,
    cut_length_s_override: float | None = None,
    custom_duration_s: float | None = None,
    debug: bool | None = None,
) -> str | None:
    client = MongoClient(MONGO_URI)
    rec = get_ableton_recording(client, project_name)
    f = rec["fields"]["ableton_recording"]

    start_cue = os.path.basename(f.get("start_sound_path", ""))
    bpm = f.get("bpm_at_start", 120)
    ts_num = f.get("ts_num", 4)
    ts_den = f.get("ts_den", 4)

    file_duration = get_audio_duration(audio_path)
    db_dur = rec["metadata"].get("duration_seconds", 0.0)
    custom = CUSTOM_DURATION_S if custom_duration_s is None else custom_duration_s
    duration = custom or file_duration or db_dur or 120.0

    bar_group = bars_per_cut or BAR_GROUP
    cut_override = cut_length_s_override if cut_length_s_override is not None else CUT_LENGTH_S
    if cut_override:
        cut_len_s = cut_override
        cut_info = f"{cut_len_s:.2f}s (manual)"
    else:
        bar_sec = 60.0 / bpm * ts_num
        cut_len_s = bar_sec * bar_group
        cut_info = f"{bar_group} bars @ {cut_len_s:.2f}s per cut"

    print(f"[info] Project '{project_name}' ({bpm} BPM, {ts_num}/{ts_den}), duration {duration:.1f}s")
    print(f"[info] Cut interval: {cut_info}")

    videos = find_videos_by_cue(client, start_cue)
    if not videos:
        print(f"[warn] No videos found with cue {start_cue}")
        return None

    seq = build_sync_sequence(videos, duration, cut_len_s)

    out_file = OUTPUT_DIR / f"{project_name.replace(' ', '_')}_sync_edit.mp4"
    renderer = FFmpegRenderer(debug=DEBUG if debug is None else debug)
    renderer.render_sequence(seq, str(out_file), str(audio_path))
    print(f"[ok] Rendered tempo-synced video -> {out_file}")
    return str(out_file)


# ==============================================================
# === CLI
# ==============================================================

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python -m music_video_generation.multi_video_generator.sync_cuts_from_recordings <project_name> <audio_file>")
        sys.exit(1)

    project = sys.argv[1]
    audio_path = Path(sys.argv[2])
    out_path = render_sync_video(project, audio_path)
    if out_path:
        print(f"[ok] Sync edit written to {out_path}")
