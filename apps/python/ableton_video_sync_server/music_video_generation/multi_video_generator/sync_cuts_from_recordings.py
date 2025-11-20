#!/usr/bin/env python3
"""
Sync-Cuts Video Generator (Tempo-Aware, file-based)
---------------------------------------------------
Renders a synchronized multi-camera video based on:

- tempo + cue info from recordings.json
- segment offsets from postprocess_matches.json
"""

from __future__ import annotations

import math
import os
from pathlib import Path
from typing import List, Optional

from .ffmpeg_render import FFmpegRenderer
from .cut import CutClip
from ..project_files import ProjectFiles, MediaInfo, RecordingInfo, make_store


OUTPUT_DIR = Path("D:/git_repos/todos/builds/sync_cuts")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

BAR_GROUP = 4
CUT_LENGTH_S = None
CUSTOM_DURATION_S = 0.0
DEBUG = True


def get_audio_duration(audio_path: Path) -> float:
    """Safe audio duration (mutagen or ffprobe)."""
    try:
        from mutagen import File as _File  # type: ignore[import]
        a = _File(audio_path)
        if a and hasattr(a, "info"):
            dur = getattr(a.info, "length", 0.0)
            if dur and dur > 0:
                return float(dur)
    except Exception:
        pass

    try:
        import subprocess
        import json as _json
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(audio_path),
        ]
        out = subprocess.check_output(cmd)
        info = _json.loads(out)
        return float(info["format"]["duration"])
    except Exception as e:
        print(f"[warn] Could not get audio duration: {e}")
        return 0.0


def get_ableton_recording(store: ProjectFiles, project_name: str) -> RecordingInfo:
    return store.get_recording_by_project(project_name)


def find_videos_by_cue(
    store: ProjectFiles,
    start_cue_path: Optional[str],
) -> List[MediaInfo]:
    if not start_cue_path:
        return []
    ref_id = os.path.basename(start_cue_path)
    return store.find_media_by_cue(ref_id)


def make_dummy_video(filename: str):
    from dataclasses import dataclass

    @dataclass
    class DummyVideo:
        filename: str

    return DummyVideo(filename)


def build_sync_sequence(
    videos: List[MediaInfo],
    song_duration: float,
    cut_len_s: float,
) -> List[CutClip]:
    """
    Given media entries, create CutClips aligned to song time.

    For each media entry, we use the first segment's `start_time_s` as the offset.
    """
    seq: List[CutClip] = []
    if not videos:
        raise RuntimeError("No postprocessing videos provided.")

    aligned = []
    for v in videos:
        path = v.file
        if not path or not os.path.exists(path):
            continue
        segs = v.segments
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
        seq.append(
            CutClip(
                video=make_dummy_video(vid_path),
                inpoint=vid_offset + start_t,
                outpoint=vid_offset + start_t + seg_duration,
                duration=seg_duration,
                time_global=start_t,
            )
        )

    print(f"[debug] Built {len(seq)} tempo-synced cuts for {song_duration:.1f}s")
    return seq


def render_sync_video(
    project_name: str,
    audio_path: Path,
    *,
    bars_per_cut: Optional[int] = None,
    cut_length_s_override: Optional[float] = None,
    custom_duration_s: Optional[float] = None,
    debug: Optional[bool] = None,
    project_root: Optional[str | Path] = None,
) -> Optional[str]:
    store = make_store(project_root, hint_path=audio_path)
    rec = get_ableton_recording(store, project_name)

    start_cue_path = rec.start_sound_path
    bpm = rec.bpm_at_start
    ts_num = rec.ts_num
    ts_den = rec.ts_den

    file_duration = get_audio_duration(audio_path)
    json_dur = rec.duration_seconds or 0.0
    custom = CUSTOM_DURATION_S if custom_duration_s is None else custom_duration_s
    duration = custom or file_duration or json_dur or 120.0

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

    videos = find_videos_by_cue(store, start_cue_path)
    if not videos:
        print(f"[warn] No videos found with start cue {start_cue_path}")
        return None

    seq = build_sync_sequence(videos, duration, cut_len_s)

    out_file = OUTPUT_DIR / f"{project_name.replace(' ', '_')}_sync_edit.mp4"
    renderer = FFmpegRenderer(debug=DEBUG if debug is None else debug)
    renderer.render_sequence(seq, str(out_file), str(audio_path))
    print(f"[ok] Rendered tempo-synced video -> {out_file}")
    return str(out_file)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print(
            "Usage: python -m music_video_generation.multi_video_generator.sync_cuts_from_recordings "
            "<project_name> <audio_file> [project_root]"
        )
        sys.exit(1)

    project = sys.argv[1]
    audio_path = Path(sys.argv[2])
    project_root_arg = Path(sys.argv[3]) if len(sys.argv) >= 4 else None

    out_path = render_sync_video(project, audio_path, project_root=project_root_arg)
    if out_path:
        print(f"[ok] Sync edit written to {out_path}")
