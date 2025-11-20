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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".m2ts", ".ts"}
AUDIO_EXTS = {".mp3", ".wav", ".flac", ".aac", ".m4a", ".ogg"}


def _infer_source_type(filename: str) -> str:
    """
    Infer a human-readable source_type from the file extension / name.

    This is only for diagnostics and debug JSON; it does NOT change behaviour
    by itself.
    """
    if not filename:
        return "unknown"

    fn = str(filename)
    ext = Path(fn).suffix.lower()

    if ext in VIDEO_EXTS:
        return "video"
    if ext in AUDIO_EXTS:
        return "audio"
    if fn.upper().startswith("BLACK"):
        return "black"

    return "unknown"


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------


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
    ) -> None:
        self.debug = debug

        if preset not in self.PRESET_OPTIONS:
            raise ValueError(f"Invalid preset '{preset}'. Must be one of {self.PRESET_OPTIONS}")

        # In debug mode we prefer very fast encoding.
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
        """
        Video filter chain for normal video sources:

        - Keep aspect ratio.
        - Pad to WxH with black.
        - Force SAR=1.
        - Constant frame rate.
        - 8-bit 4:2:0.
        """
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
    ) -> None:
        """
        Run ffmpeg and (optionally) show progress in a tqdm bar.

        On error, we log the last bit of ffmpeg output to help debugging.
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
        last_lines: list[str] = []

        try:
            if proc.stdout is not None:
                for line in proc.stdout:
                    line = line.rstrip("\n")
                    if not line:
                        continue

                    # keep a short tail for error reporting
                    last_lines.append(line)
                    if len(last_lines) > 10:
                        last_lines.pop(0)

                    # Parse ffmpeg "out_time_ms" progress line
                    if line.startswith("out_time_ms="):
                        try:
                            ms = int(line.split("=", 1)[1])
                            cur = ms / 1_000_000.0
                            if bar and total_seconds is not None:
                                bar.n = min(cur, total_seconds)
                                bar.refresh()
                        except Exception:
                            # best-effort only
                            pass
                    elif line.startswith("progress=") and line.endswith("end"):
                        break
        finally:
            proc.wait()
            if bar:
                bar.n = bar.total or bar.n
                bar.close()

        if proc.returncode != 0:
            last_output = "\n".join(last_lines)
            log.error(
                "FFmpeg failed with exit code %s during '%s'. Last output:\n%s",
                proc.returncode,
                desc,
                last_output,
            )
            raise RuntimeError(f"ffmpeg failed with exit code {proc.returncode}")

    # ---------- public API ----------

    def extract_segment(self, clip: CutClip, out_path: str, desc: Optional[str] = None) -> None:
        """
        Simple single-segment extract (with re-encode).
        Not used by the sync pipeline, but kept for completeness.
        """
        cmd = [
            "-i",
            clip.video.filename,
            "-ss",
            f"{clip.inpoint:.6f}",
            "-t",
            f"{clip.duration:.6f}",
            "-vf",
            self._vf_chain(),
            *self._encode_args(),
            out_path,
        ]
        self._run_ffmpeg_with_progress(
            cmd,
            total_seconds=clip.duration,
            desc=desc or "Extract",
            leave=False,
        )

    def concat_segments(self, segment_paths: List[str], out_path: str, total_duration: Optional[float] = None) -> None:
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

    def render_sequence(self, seq: List[CutClip], output_path: str, audio_source: Optional[str] = None) -> str:
        """
        Core multi-clip render:

        - Writes per-clip segments to a working directory.
        - Concatenates them into a temp video.
        - Optionally muxes a separate master audio file.
        - Writes a `<output_base>_plan.json` next to the final output,
          containing rich metadata for debugging.
        """
        if not seq:
            raise ValueError("Empty cut sequence.")

        base, _ = os.path.splitext(output_path)
        final_output = f"{base}.{self.container_ext}"

        # Workdir – we currently assume a fast local path; if /dev/shm does not
        # exist on this platform, this will simply be a normal directory.
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

        # ------------------------------------------------------------------
        # Write debug plan JSON *before* rendering, so we can inspect decisions
        # even if ffmpeg fails.
        # ------------------------------------------------------------------
        plan_path = f"{base}_plan.json"
        try:
            debug_rows = []
            for idx, clip in enumerate(seq, start=1):
                filename = getattr(clip.video, "filename", None)
                debug_rows.append(
                    {
                        "index": idx,
                        "time_global": float(clip.time_global),
                        "duration": float(clip.duration),
                        "inpoint": float(clip.inpoint),
                        "filename": filename,
                        "source_type": _infer_source_type(str(filename) if filename is not None else ""),
                    }
                )

            plan_payload = {
                "output_file": final_output,
                "audio_source": audio_source,
                "width": self.width,
                "height": self.height,
                "fps": self.fps,
                "crf": self.crf,
                "preset": self.preset,
                "use_nvenc": self.use_nvenc,
                "container_ext": self.container_ext,
                "total_clips": len(seq),
                "total_video_duration": total_video_duration,
                "segments": debug_rows,
            }

            with open(plan_path, "w", encoding="utf-8") as f:
                json.dump(plan_payload, f, indent=2)

            log.info("render_sequence: wrote debug plan to %s", plan_path)
        except Exception as exc:  # debug only – do not block rendering
            log.warning("render_sequence: failed to write debug plan JSON (%s)", exc)

        # ------------------------------------------------------------------
        # Parallel segment extraction (LIMITED WORKERS, no audio in temp clips)
        # ------------------------------------------------------------------

        def worker(i: int, clip: CutClip) -> str:
            filename = getattr(clip.video, "filename", "")
            src_type = _infer_source_type(filename)
            seg_path = os.path.join(workdir, f"seg_{i:04d}.{self.container_ext}")

            if src_type == "audio":
                # Audio-only input: synthesize a black video segment of the right duration.
                # We do NOT use the audio here; it's purely visual padding. The master
                # audio will be muxed at the end from `audio_source`.
                filter_spec = (
                    f"color=c=black:s={self.width}x{self.height}:r={self.fps}:d={clip.duration:.6f}"
                )
                cmd = [
                    "-f",
                    "lavfi",
                    "-i",
                    filter_spec,
                    *self._encode_args(),
                    seg_path,
                ]
                desc = f"Segment {i}/{len(seq)} (audio->black)"
                show_progress = False
            else:
                # Normal video input (or anything ffmpeg can treat as video)
                cmd = [
                    "-i",
                    filename,
                    "-ss",
                    f"{clip.inpoint:.6f}",
                    "-t",
                    f"{clip.duration:.6f}",
                    "-vf",
                    self._vf_chain(),
                    *self._encode_args(),
                    "-an",  # drop audio in the temp segment
                    seg_path,
                ]
                desc = f"Segment {i}/{len(seq)}"
                show_progress = False

            self._run_ffmpeg_with_progress(
                cmd,
                total_seconds=clip.duration,
                desc=desc,
                leave=False,
                show_progress=show_progress,
            )
            return seg_path

        max_workers = min(2, os.cpu_count() or 1)
        log.info("render_sequence: starting extraction with max_workers=%d", max_workers)

        segments: List[str] = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(worker, i, clip) for i, clip in enumerate(seq, start=1)]
            # tqdm wrapper for high-level progress over segments
            if tqdm is not None:
                iterator = tqdm(as_completed(futures), desc="Segments", total=len(futures))
            else:
                iterator = as_completed(futures)

            for future in iterator:
                segments.append(future.result())

        # keep segments in deterministic order: seg_0001, seg_0002, ...
        segments.sort()

        # ------------------------------------------------------------------
        # Concatenate temp segments
        # ------------------------------------------------------------------
        temp_video = os.path.join(workdir, f"temp_video.{self.container_ext}")
        self.concat_segments(segments, temp_video, total_duration=total_video_duration)

        # ------------------------------------------------------------------
        # Final audio mux (master audio is applied here)
        # ------------------------------------------------------------------
        if audio_source:
            cmd = [
                "-i",
                temp_video,
                "-i",
                audio_source,
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-c:v",
                "copy",  # no re-encode of video
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
                show_progress=False,
            )
        else:
            shutil.move(temp_video, final_output)

        return final_output
