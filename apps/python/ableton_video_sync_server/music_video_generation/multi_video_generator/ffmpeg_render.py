from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Optional

from .cut import CutClip

try:
    from tqdm import tqdm
except Exception:  # fallback if tqdm isn't installed
    tqdm = None

log = logging.getLogger(__name__)


class FFmpegRenderer:
    PRESET_OPTIONS = [
        "ultrafast",  # fastest encode, worst compression
        "superfast",
        "veryfast",
        "faster",
        "fast",
        "medium",  # default in ffmpeg
        "slow",
        "slower",
        "veryslow",  # best compression, slowest
        "placebo",  # insanely slow, no practical benefit
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

        # In debug mode we prefer ultrafast encodes
        self.preset = "ultrafast" if self.debug else preset
        self.width = width
        self.height = height
        self.fps = fps
        self.crf = crf
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
                "-c:v",
                "h264_nvenc",
                "-rc",
                "constqp",
                "-qp",
                "21",  # roughly CRF~20; lower = better
                "-preset",
                f"p{1 if self.debug else 4}",  # p5 better, p1 fastest
                "-tune",
                "hq",
                "-pix_fmt",
                "yuv420p",
                "-bf",
                "3",
                "-c:a",
                "aac",
                "-b:a",
                self.audio_bitrate,
                "-ar",
                str(self.sample_rate),
                "-ac",
                "2",
                "-movflags",
                "+faststart",
                "-fps_mode",
                "cfr",
            ]
        else:
            return [
                "-c:v",
                "libx264",
                "-crf",
                str(self.crf),
                "-preset",
                self.preset,
                "-pix_fmt",
                "yuv420p",
                "-g",
                str(self.fps * 2),  # ~2s GOP
                "-keyint_min",
                str(self.fps * 2),
                "-sc_threshold",
                "0",
                "-c:a",
                "aac",
                "-b:a",
                self.audio_bitrate,
                "-ar",
                str(self.sample_rate),
                "-ac",
                "2",
                "-movflags",
                "+faststart",
                "-fps_mode",
                "cfr",
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
        show_progress: bool = True,
    ):
        """
        Run ffmpeg with '-progress pipe:1', optionally showing a tqdm bar.

        On failure:
          - Logs last lines of ffmpeg output for easier debugging.
          - Raises RuntimeError.
        """
        base = ["ffmpeg", "-hide_banner", "-y", "-loglevel", "error", "-progress", "pipe:1"]
        full_cmd = base + cmd

        log.info("FFmpeg call (%s): %s", desc, " ".join(full_cmd))

        proc = subprocess.Popen(
            full_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1,
        )

        use_bar = show_progress and (tqdm is not None) and (total_seconds is not None) and self.debug
        bar = tqdm(total=total_seconds, desc=desc, unit="s", leave=leave) if use_bar else None

        cur = 0.0
        last_lines: List[str] = []

        try:
            if proc.stdout is not None:
                for line in proc.stdout:
                    line = line.strip()
                    if line:
                        # keep last few lines for error context
                        last_lines.append(line)
                        if len(last_lines) > 20:
                            last_lines.pop(0)

                    # Parse ffmpeg progress key/vals
                    if line.startswith("out_time_ms="):
                        try:
                            ms = int(line.split("=", 1)[1])
                            cur = ms / 1_000_000.0
                            if bar and total_seconds is not None:
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
            log.error(
                "FFmpeg failed with exit code %s during '%s'. Last output:\n%s",
                proc.returncode,
                desc,
                "\n".join(last_lines),
            )
            raise RuntimeError(f"ffmpeg failed with exit code {proc.returncode}")

    # ---------- API ----------

    def extract_segment(self, clip: CutClip, out_path: str, desc: Optional[str] = None):
        """
        Simple “one clip” extract. Currently unused in the main sync pipeline,
        but kept for completeness.
        """
        # Explicit black filler support
        is_black = getattr(clip.video, "kind", None) == "black"

        if is_black:
            log.info(
                "extract_segment: BLACK filler segment (duration=%.3fs) to %s",
                clip.duration,
                out_path,
            )
            input_args = [
                "-f",
                "lavfi",
                "-i",
                f"color=c=black:size={self.width}x{self.height}:rate={self.fps}",
            ]
        else:
            input_path = clip.video.filename

            # Decide if this is a likely audio-only source
            suffix = str(input_path).lower()
            is_audio_like = suffix.endswith(
                (".mp3", ".wav", ".flac", ".aac", ".m4a", ".ogg", ".wma")
            )

            if is_audio_like:
                log.warning(
                    "extract_segment: source %s looks like audio-only; using black video filler.",
                    input_path,
                )
                input_args = [
                    "-f",
                    "lavfi",
                    "-i",
                    f"color=c=black:size={self.width}x{self.height}:rate={self.fps}",
                ]
            else:
                input_args = ["-i", input_path]

        cmd = [
            *input_args,
            "-ss",
            f"{clip.inpoint:.6f}",
            "-t",
            f"{clip.duration:.6f}",
            "-vf",
            self._vf_chain(),
            *self._encode_args(),
            "-an",  # we do not want per-segment audio here
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
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            list_file,
            *self._encode_args(),
            out_path,
        ]
        self._run_ffmpeg_with_progress(
            cmd,
            total_seconds=total_duration,
            desc="Concat",
            leave=False,
        )

    def render_sequence(
        self,
        seq: List["CutClip"],
        output_path: str,
        audio_source: Optional[str] = None,
        audio_offset_s: float = 0.0,
    ) -> str:        
        """
        Main entry point: render a sequence of CutClip objects to a final video.

        Steps:
          1) Extract each clip to a temp segment (video-only).
             - Real video sources are re-encoded.
             - Audio-like “sources” (.mp3/.wav/..) become black filler.
             - Clips with video.kind == 'black' use a synthetic black source.
          2) Concat all segments to a temp video.
          3) Mux final audio from audio_source (if provided).
          4) Write an *_plan.json next to output_path with rich metadata.
        """
        if not seq:
            raise ValueError("Empty cut sequence.")

        base, _ = os.path.splitext(output_path)
        final_output = f"{base}.{self.container_ext}"

        # Workdir (acts as a temp directory)
        workdir = "/dev/shm/cuts"
        os.makedirs(workdir, exist_ok=True)

        # Precompute durations
        total_video_duration = sum(float(c.duration) for c in seq)

        log.info(
            "render_sequence: workdir=%s final_output=%s audio_source=%s",
            workdir,
            final_output,
            audio_source,
        )
        log.info(
            "render_sequence: %d clips, total_video_duration=%.3fs",
            len(seq),
            total_video_duration,
        )

        # ----- Build plan skeleton (will be written as *_plan.json) -----
        plan_base, _ = os.path.splitext(output_path)
        plan_path = Path(f"{plan_base}_plan.json")
        plan_data: dict = {
            "kind": "ffmpeg_segment_plan",
            "version": 1,
            "output": str(Path(final_output).expanduser().resolve()),
            "width": self.width,
            "height": self.height,
            "fps": self.fps,
            "crf": self.crf,
            "preset": self.preset,
            "use_nvenc": self.use_nvenc,
            "audio_source": str(audio_source) if audio_source is not None else None,
            "total_clips": len(seq),
            "total_video_duration": total_video_duration,
            "segments": [],
        }

        # --- Parallel segment extraction (limited workers, no audio) ---
        def worker(i: int, clip: CutClip) -> str:
            seg_path = os.path.join(workdir, f"seg_{i:04d}.{self.container_ext}")
            src = getattr(clip.video, "filename", "__BLACK__")
            suffix = str(src).lower()

            is_black = getattr(clip.video, "kind", None) == "black"
            if is_black:
                log.info(
                    "render_sequence: clip %d is BLACK filler (duration=%.3fs).",
                    i,
                    clip.duration,
                )
                input_args = [
                    "-f",
                    "lavfi",
                    "-i",
                    f"color=c=black:size={self.width}x{self.height}:rate={self.fps}",
                ]
                is_audio_like = False
            else:
                is_audio_like = suffix.endswith(
                    (".mp3", ".wav", ".flac", ".aac", ".m4a", ".ogg", ".wma")
                )

                if is_audio_like:
                    log.warning(
                        "render_sequence: clip %d source %s looks audio-only; using black video filler.",
                        i,
                        src,
                    )
                    input_args = [
                        "-f",
                        "lavfi",
                        "-i",
                        f"color=c=black:size={self.width}x{self.height}:rate={self.fps}",
                    ]
                else:
                    input_args = ["-i", src]

            cmd = [
                *input_args,
                "-ss",
                f"{clip.inpoint:.6f}",
                "-t",
                f"{clip.duration:.6f}",
                "-vf",
                self._vf_chain(),
                *self._encode_args(),
                "-an",  # no per-segment audio
                seg_path,
            ]

            self._run_ffmpeg_with_progress(
                cmd,
                total_seconds=clip.duration,
                desc=f"Segment {i}/{len(seq)}",
                leave=False,
                show_progress=False,  # avoid tons of bars
            )

            # Fill per-segment plan metadata
            plan_data["segments"].append(
                {
                    "index": i,
                    "segment_output": seg_path,
                    "source": str(src),
                    "inpoint": float(clip.inpoint),
                    "duration": float(clip.duration),
                    "time_global": float(getattr(clip, "time_global", 0.0)),
                    "camera_id": getattr(clip.video, "camera_id", None),
                    "kind": getattr(clip.video, "kind", None),
                    "is_audio_like": is_audio_like,
                }
            )

            return seg_path

        max_workers = min(2, os.cpu_count() or 2)
        log.info("render_sequence: starting extraction with max_workers=%d", max_workers)

        segments: List[str] = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(worker, i, clip) for i, clip in enumerate(seq, start=1)]
            if tqdm is not None:
                for future in tqdm(as_completed(futures), desc="Segments", total=len(futures)):
                    segments.append(future.result())
            else:
                for future in as_completed(futures):
                    segments.append(future.result())

        # Keep segments in order by filename (seg_0001, seg_0002, ...)
        segments.sort()

        # Add segment paths to plan
        plan_data["segment_paths"] = segments

        # --- Concatenate ---
        temp_video = os.path.join(workdir, f"temp_video.{self.container_ext}")
        self.concat_segments(segments, temp_video, total_duration=total_video_duration)

        # --- Final audio mux ---
        if audio_source:
            cmd = [
                "-i",
                temp_video,
                "-ss", f"{audio_offset_s:.6f}",

                "-i",
                audio_source,
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-c:v",
                "copy",  # video stream copy after concat
                "-c:a",
                "aac",
                "-b:a",
                self.audio_bitrate,
                "-ar",
                str(self.sample_rate),
                "-ac",
                "2",
                "-shortest",
                "-movflags",
                "+faststart",
                final_output,
            ]
            self._run_ffmpeg_with_progress(
                cmd,
                total_seconds=total_video_duration,
                desc="Mux audio",
                leave=False,
                show_progress=True,
            )
        else:
            shutil.move(temp_video, final_output)

        # --- Persist plan JSON (best-effort) ---
        try:
            plan_path.parent.mkdir(parents=True, exist_ok=True)
            with open(plan_path, "w", encoding="utf-8") as f:
                json.dump(plan_data, f, indent=2)
            log.info("render_sequence: wrote ffmpeg plan JSON to %s", plan_path)
        except Exception as exc:
            log.warning("render_sequence: failed to write plan JSON (%s)", exc)

        return final_output
