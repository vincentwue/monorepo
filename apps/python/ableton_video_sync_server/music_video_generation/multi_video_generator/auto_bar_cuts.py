#!/usr/bin/env python3
"""
Auto-Bar-Cut Video Generator (file-based)
-----------------------------------------
Renders a synchronized multi-camera video with automatic cuts every N bars.

Reads:
- tempo / TS and recording info from recordings.json
- only uses the audio file duration for final length (with small override option)
"""

from __future__ import annotations

import math
import random
from pathlib import Path
from typing import List, Optional

from mutagen import File as AudioFile  # type: ignore[import]

from .ffmpeg_render import FFmpegRenderer
from .cut import CutClip
from ..project_files import ProjectFiles, make_store


BAR_GROUP = 4
CUSTOM_DURATION_S = 15.0          # set to 0.0 to use full track
OUTPUT_DIR = Path("D:/git_repos/todos/builds/auto_bar_cuts")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def get_audio_duration(audio_path: Path) -> float:
    """Reads actual duration of an audio file (MP3/WAV) robustly."""
    try:
        audio = AudioFile(audio_path)
        if audio and hasattr(audio, "info") and getattr(audio.info, "length", 0) > 0:
            return float(audio.info.length)
    except Exception:
        pass

    # ffprobe fallback
    try:
        import subprocess
        import json as _json
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json", str(audio_path),
        ]
        out = subprocess.check_output(cmd)
        info = _json.loads(out)
        return float(info["format"]["duration"])
    except Exception as e:
        print(f"[warn] Could not determine duration for {audio_path}: {e}")
        return 0.0


def get_recording_data(
    store: ProjectFiles,
    project_name: str,
    audio_path: Path,
    custom_duration_s: Optional[float] = None,
):
    rec = store.get_recording_by_project(project_name)

    bpm = rec.bpm_at_start
    ts_num = rec.ts_num
    ts_den = rec.ts_den

    json_dur = rec.duration_seconds or 0.0
    file_duration = get_audio_duration(audio_path)

    custom = CUSTOM_DURATION_S if custom_duration_s is None else custom_duration_s
    if custom and custom > 0:
        duration = custom
        source = "custom"
    else:
        duration = max(json_dur, file_duration, 1.0)
        source = "file" if file_duration >= json_dur else "json"

    print(
        f"[info] Recording '{project_name}': {bpm} BPM, {ts_num}/{ts_den}, "
        f"{duration:.2f}s (source={source}, file={file_duration:.2f}s, json={json_dur:.2f}s)"
    )
    return bpm, ts_num, ts_den, duration


def compute_cut_points(bpm: float, ts_num: int, duration: float, bars_per_cut: int = BAR_GROUP):
    bar_sec = 60.0 / bpm * ts_num
    cut_interval = bar_sec * bars_per_cut
    total_cuts = max(1, math.ceil(duration / cut_interval))
    cut_points = [i * cut_interval for i in range(total_cuts)]
    print(f"[info] {total_cuts} cuts @ every {bars_per_cut} bars ({cut_interval:.2f}s each)")
    return cut_points, cut_interval


def find_video_clips(video_dir: Path, exts=(".mp4", ".mov", ".mkv")) -> List[str]:
    clips = [str(p) for p in video_dir.rglob("*") if p.suffix.lower() in exts]
    if not clips:
        raise RuntimeError(f"No video clips found in {video_dir}")
    print(f"[info] Found {len(clips)} video sources")
    return clips


def generate_bar_cuts_sequence(
    videos: List[str],
    cut_points: List[float],
    duration: float,
    segment_length: float,
) -> List[CutClip]:
    from dataclasses import dataclass

    @dataclass
    class DummyVideo:
        filename: str

    seq: List[CutClip] = []
    if not videos:
        raise RuntimeError("No video sources provided to generate sequence.")

    for start in cut_points:
        start_t = start
        end_t = min(duration, start_t + segment_length)
        seg_duration = end_t - start_t
        if seg_duration <= 0:
            continue

        vid = random.choice(videos)
        seq.append(
            CutClip(
                video=DummyVideo(vid),
                inpoint=0.0,
                outpoint=seg_duration,
                duration=seg_duration,
                time_global=start_t,
            )
        )

    if not seq:
        vid = random.choice(videos)
        seq.append(
            CutClip(
                video=DummyVideo(vid),
                inpoint=0.0,
                outpoint=duration,
                duration=duration,
                time_global=0.0,
            )
        )
        print("[warn] No valid cuts computed, fallback to single full-length clip.")

    print(f"[debug] Generated {len(seq)} segments (~{duration:.2f}s total)")
    return seq


def render_auto_bar_video(
    project_name: str,
    video_dir: Path,
    audio_path: Path,
    *,
    bars_per_cut: Optional[int] = None,
    custom_duration_s: Optional[float] = None,
    project_root: Optional[str | Path] = None,
) -> str:
    store = make_store(project_root, hint_path=audio_path)

    bpm, ts_num, ts_den, duration = get_recording_data(
        store,
        project_name,
        audio_path,
        custom_duration_s=custom_duration_s,
    )

    bars = bars_per_cut or BAR_GROUP
    cuts, seg_len = compute_cut_points(bpm, ts_num, duration, bars_per_cut=bars)
    videos = find_video_clips(video_dir)
    print(f"[debug] duration={duration:.2f}s, bpm={bpm}, ts={ts_num}/{ts_den}")

    seq = generate_bar_cuts_sequence(videos, cuts, duration, seg_len)

    out_file = OUTPUT_DIR / f"{project_name.replace(' ', '_')}_autoedit.mp4"
    renderer = FFmpegRenderer(debug=True)
    final = renderer.render_sequence(seq, str(out_file), str(audio_path))
    print(f"[ok] Rendered: {final}")
    return final


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 4:
        print(
            "Usage: python -m music_video_generation.multi_video_generator.auto_bar_cuts "
            "<project_name> <video_dir> <audio_file> [project_root]"
        )
        sys.exit(1)

    project = sys.argv[1]
    video_dir = Path(sys.argv[2])
    audio_path = Path(sys.argv[3])
    project_root_arg = Path(sys.argv[4]) if len(sys.argv) >= 5 else None

    result_path = render_auto_bar_video(project, video_dir, audio_path, project_root=project_root_arg)
    print(f"[ok] Auto bar edit written to {result_path}")
