from __future__ import annotations

import subprocess
from pathlib import Path
from typing import List

from loguru import logger


def run_ffmpeg(
    video: Path,
    audio: Path,
    trim_start: float,
    total_duration: float,
    pad_start: float,
    pad_end: float,
    output: Path,
) -> None:
    """
    Encode an aligned video:

    - seek into the video by trim_start
    - tpad adds black at head/tail (pad_start/pad_end)
    - entire output is `total_duration` seconds long,
      with the master audio as audio track 1.
    """
    output.parent.mkdir(parents=True, exist_ok=True)

    filters: List[str] = []
    if pad_start > 1e-3 or pad_end > 1e-3:
        params = ["color=black"]
        if pad_start > 1e-3:
            params.append("start_mode=add")
            params.append(f"start_duration={pad_start:.3f}")
        if pad_end > 1e-3:
            params.append("stop_mode=add")
            params.append(f"stop_duration={pad_end:.3f}")
        filters.append("tpad=" + ":".join(params))

    cmd: List[str] = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-ss",
        f"{trim_start:.3f}",
        "-i",
        str(video),
        "-i",
        str(audio),
    ]

    if filters:
        cmd += ["-vf", ",".join(filters)]

    cmd += [
        "-t",
        f"{total_duration:.3f}",
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "20",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-shortest",
        str(output),
    ]

    logger.info(
        "Aligning %s -> %s (trim=%.3fs pad_start=%.3fs pad_end=%.3fs)",
        video,
        output,
        trim_start,
        pad_start,
        pad_end,
    )
    subprocess.run(cmd, check=True)
