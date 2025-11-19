import os
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import List, Optional

import subprocess
from .cut import CutClip
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional
import os
import shutil

try:
    from tqdm import tqdm
except Exception:  # fallback if tqdm isn't installed
    tqdm = None

class FFmpegRenderer:
    PRESET_OPTIONS = [
        "ultrafast",  # fastest encode, worst compression
        "superfast",
        "veryfast",
        "faster",
        "fast",
        "medium",     # default in ffmpeg
        "slow",
        "slower",
        "veryslow",   # best compression, slowest
        "placebo",    # insanely slow, no practical benefit
    ]

    def __init__(
        self,
        width: int = 1920,
        height: int = 1080,
        fps: int = 30,
        crf: int = 20,
        preset: str = "medium",
        audio_bitrate: str = "160k",
        sample_rate: int = 48000,
        use_nvenc: bool = False,
        container_ext: str = "mp4",
        debug: bool = True,
    ):
        self.debug = debug
        if preset not in self.PRESET_OPTIONS:
            raise ValueError(f"Invalid preset '{preset}'. Must be one of {self.PRESET_OPTIONS}")

        self.preset = preset if not self.debug else "ultrafast"
        self.width = width
        self.height = height
        self.fps = fps
        self.crf = crf
        self.preset = preset
        self.audio_bitrate = audio_bitrate
        self.sample_rate = sample_rate
        self.use_nvenc = use_nvenc
        self.container_ext = container_ext

    # ---------- ffmpeg helpers ----------

    def _vf_chain(self) -> str:
        # Keep AR, pad to WxH, force SAR=1, CFR fps, and 8-bit 4:2:0
        return (
            f"scale={self.width}:{self.height}:force_original_aspect_ratio=decrease,"
            f"pad={self.width}:{self.height}:(ow-iw)/2:(oh-ih)/2:color=black,"
            "setsar=1,"
            f"fps={self.fps},"
            "format=yuv420p"
        )

    def _encode_args(self) -> List[str]:
        if self.use_nvenc:
            # Very fast, good quality
            return [
                "-c:v", "h264_nvenc",
                "-rc", "constqp",
                "-qp", "21",  # roughly CRF~20; lower = better
                "-preset", f"p{1 if self.debug else 4}",  # p5 better, p1 fastest
                "-tune", "hq",
                "-pix_fmt", "yuv420p",
                "-bf", "3",
                "-c:a", "aac",
                "-b:a", self.audio_bitrate,
                "-ar", str(self.sample_rate),
                "-ac", "2",
                "-movflags", "+faststart",
                "-fps_mode", "cfr",
            ]
        else:
            return [
                "-c:v", "libx264",
                "-crf", str(self.crf),
                "-preset", self.preset,
                "-pix_fmt", "yuv420p",
                "-g", str(self.fps * 2),            # ~2s GOP
                "-keyint_min", str(self.fps * 2),
                "-sc_threshold", "0",
                "-c:a", "aac",
                "-b:a", self.audio_bitrate,
                "-ar", str(self.sample_rate),
                "-ac", "2",
                "-movflags", "+faststart",
                "-fps_mode", "cfr",
            ]

    def _ffconcat_quote(self, p: str) -> str:
        posix = Path(p).as_posix()
        return "'" + posix.replace("'", r"'\''") + "'"

    def _run_ffmpeg_with_progress(
            self,
            cmd: List[str],
            total_seconds: float | None,
            desc: str,
            leave: bool = False,
            show_progress: bool = True,  # <--- NEU
    ):
        base = ["ffmpeg", "-hide_banner", "-y", "-loglevel", "error", "-progress", "pipe:1"]
        full_cmd = base + cmd

        proc = subprocess.Popen(
            full_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1,
        )
        # print(f"show_progress: {show_progress}, tqdm=none: {tqdm is None}, total_seconds: {total_seconds}, debug: {self.debug}")
        use_bar = show_progress and (tqdm is not None) and (total_seconds is not None) and self.debug
        bar = tqdm(total=total_seconds, desc=desc, unit="s", leave=leave) if use_bar else None

        cur = 0.0
        try:
            if proc.stdout is not None:
                for line in proc.stdout:
                    line = line.strip()
                    # Parse ffmpeg progress key/vals
                    if line.startswith("out_time_ms="):
                        try:
                            ms = int(line.split("=", 1)[1])
                            cur = ms / 1_000_000.0
                            if bar:
                                bar.n = min(cur, total_seconds)
                                bar.refresh()
                        except Exception:
                            pass
                    elif line.startswith("progress=") and line.endswith("end"):
                        break
        finally:
            proc.wait()
            if bar:
                bar.n = bar.total or bar.n
                bar.close()
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg failed with exit code {proc.returncode}")

    # ---------- API ----------

    def extract_segment(self, clip: CutClip, out_path: str, desc: Optional[str] = None):
        cmd = [
            # INPUT FIRST (accurate seek happens after -i)
            "-i", clip.video.filename,
            "-ss", f"{clip.inpoint:.6f}",
            "-t",  f"{clip.duration:.6f}",
            "-vf", self._vf_chain(),
            *self._encode_args(),
            out_path,
        ]
        self._run_ffmpeg_with_progress(
            cmd,
            total_seconds=clip.duration,
            desc=desc or "Extract",
            leave=False,
        )

    def concat_segments(self, segment_paths: List[str], out_path: str, total_duration: Optional[float] = None):
        if not segment_paths:
            raise ValueError("No segments to concat.")

        list_file = os.path.join(os.path.dirname(segment_paths[0]), "concat.txt")
        with open(list_file, "w", encoding="utf-8", newline="\n") as f:
            for p in segment_paths:
                f.write(f"file {self._ffconcat_quote(p)}\n")

        cmd = [
            "-f", "concat",
            "-safe", "0",
            "-i", list_file,
            *self._encode_args(),
            out_path,
        ]
        self._run_ffmpeg_with_progress(
            cmd,
            total_seconds=total_duration,
            desc="Concat",
            leave=False,
        )

    def render_sequence(self, seq: List["CutClip"], output_path: str, audio_source: Optional[str] = None) -> str:
        if not seq:
            raise ValueError("Empty cut sequence.")


        
        base, _ = os.path.splitext(output_path)
        final_output = f"{base}.{self.container_ext}"

        # Workdir in RAM-Disk
        workdir = "/dev/shm/cuts"
        os.makedirs(workdir, exist_ok=True)

        # Precompute durations
        total_video_duration = sum(float(c.duration) for c in seq)

        # --- Parallel segment extraction (LIMITED WORKERS, no audio) ---
        def worker(i: int, clip) -> str:
            seg_path = os.path.join(workdir, f"seg_{i:04d}.{self.container_ext}")
            self._run_ffmpeg_with_progress(
                [
                    "-i", clip.video.filename,
                    "-ss", f"{clip.inpoint:.6f}",
                    "-t", f"{clip.duration:.6f}",
                    "-vf", self._vf_chain(),
                    *self._encode_args(),
                    "-an",  # <--- kein Audio, schneller
                    seg_path,
                ],
                total_seconds=clip.duration,
                desc=f"Segment {i}/{len(seq)}",
                show_progress=False,  # weniger Bars
            )
            return seg_path

        max_workers = min(2, os.cpu_count())  # <--- Limit
        segments: List[str] = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(worker, i, clip) for i, clip in enumerate(seq, start=1)]
            for future in tqdm(as_completed(futures), desc="Segments", total=len(futures)):
                segments.append(future.result())

        segments.sort()

        # --- Concatenate ---
        temp_video = os.path.join(workdir, f"temp_video.{self.container_ext}")
        self.concat_segments(segments, temp_video, total_duration=total_video_duration)

        # --- Final audio mux ---
        if audio_source:
            cmd = [
                "-i", temp_video,
                "-i", audio_source,
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-c:v", "copy",  # Video stream copy
                "-c:a", "aac",
                "-b:a", self.audio_bitrate,
                "-ar", str(self.sample_rate),
                "-ac", "2",
                "-shortest",
                "-movflags", "+faststart",
                final_output,
            ]
            self._run_ffmpeg_with_progress(cmd, total_seconds=total_video_duration, desc="Mux audio")
        else:
            shutil.move(temp_video, final_output)

        return final_output