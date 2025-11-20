from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Dict, Optional, List
from loguru import logger

from .audio import resolve_audio, probe_duration
from .io import load_postprocess, load_recordings, read_state, write_state
from .utils import find_start_cue
from .video import run_ffmpeg
from .match import find_recording_for_segment


VIDEO_EXTS = (".mp4", ".mkv", ".mov", ".ts", ".mts", ".m4v", ".avi", ".webm")


class FootageAlignService:

    # ---------------------------------------------------------
    # Public API
    # ---------------------------------------------------------
    def align(self, project_path: str, *, audio_path: Optional[str] = None) -> Dict:
        root = self._resolve_project(project_path)

        audio = resolve_audio(root, audio_path)
        audio_dur = probe_duration(audio)

        post = load_postprocess(root)
        media_entries = post.get("media") or []

        recordings = load_recordings(root)

        # find audio cue
        audio_entry = self._find_postprocess_entry_for_path(media_entries, audio)
        if not audio_entry:
            raise RuntimeError("Audio not part of postprocess—run postprocess again.")

        audio_cue = find_start_cue(audio_entry)
        if audio_cue is None:
            raise RuntimeError("No start cue in audio; cannot align.")

        logger.info("Aligning: audio cue at %.3fs", audio_cue)

        output_dir = root / "generated" / "aligned"
        results = []
        debug = []

        # -----------------------------------------
        # per-video/per-segment alignment
        # -----------------------------------------
        for entry in media_entries:
            f = entry.get("file")
            if not f:
                continue
            video = Path(f)
            if video.suffix.lower() not in VIDEO_EXTS:
                continue
            if not video.exists():
                continue

            segments = entry.get("segments") or []
            if not segments:
                continue

            video_dur = probe_duration(video)

            # match recording early (may fallback later)
            start_hits = entry.get("start_hits", [])
            end_hits = entry.get("end_hits", [])

            matched_recording = find_recording_for_segment(
                seg_start=segments[0].get("start_time_s", 0),
                seg_end=segments[0].get("end_time_s"),
                start_hits=start_hits,
                end_hits=end_hits,
                recordings=recordings,
            )

            for seg in segments:
                seg_index = int(seg.get("index") or 0)
                seg_start = float(seg["start_time_s"])
                seg_end = seg.get("end_time_s")
                seg_end = float(seg_end) if isinstance(seg_end, (int, float)) else None

                # compute relative offset
                relative_offset = seg_start - audio_cue
                trim_start = max(0.0, relative_offset)
                pad_start = max(0.0, -relative_offset)

                # segment duration
                if seg_end is not None:
                    seg_duration = max(0.0, seg_end - seg_start)
                else:
                    seg_duration = max(0.0, video_dur - seg_start)

                available = min(seg_duration, max(0.0, video_dur - trim_start))
                if available < 0.25:
                    continue

                # audio usable portion
                usable_audio = max(0.0, audio_dur - pad_start)
                used_duration = min(usable_audio, available)
                pad_end = max(0.0, audio_dur - pad_start - used_duration)

                out_file = output_dir / f"{video.stem}_seg{seg_index:03d}_aligned.mp4"
                run_ffmpeg(video, audio, trim_start, audio_dur, pad_start, pad_end, out_file)

                meta = {
                    "source_video": str(video),
                    "segment_index": seg_index,
                    "segment_start_s": seg_start,
                    "segment_end_s": seg_end,
                    "segment_duration_s": seg_duration,
                    "trim_start": trim_start,
                    "pad_start": pad_start,
                    "pad_end": pad_end,
                    "used_duration": used_duration,
                    "output_path": str(out_file),
                    "flags": {
                        "missing_end": bool(seg.get("edge_case") == "missing_end"),
                        "too_short": used_duration < 1.0,
                        "usable": used_duration >= 1.0,
                        "confidence": 0.0,
                    },
                }

                # attach Ableton recording metadata
                if matched_recording:
                    meta["recording_id"] = matched_recording.get("id")
                    meta["track_names"] = matched_recording.get("recording_track_names", [])
                    meta["recording_start_sound"] = matched_recording.get("start_sound_path")
                    meta["recording_end_sound"] = matched_recording.get("end_sound_path")
                else:
                    meta["recording_id"] = None
                    meta["track_names"] = []
                    meta["recording_start_sound"] = None
                    meta["recording_end_sound"] = None

                results.append(meta)

                debug.append({
                    "file": str(video),
                    "segment_index": seg_index,
                    "video_cue": seg_start,
                    "audio_cue": audio_cue,
                    "relative_offset": relative_offset,
                    "trim_start": trim_start,
                    "pad_start": pad_start,
                    "pad_end": pad_end,
                    "video_duration": video_dur,
                    "segment_end_s": seg_end,
                    "segment_duration_s": seg_duration,
                    "used_duration": used_duration,
                })

        payload = {
            "project_path": str(root),
            "audio_path": str(audio),
            "audio_duration": audio_dur,
            "output_dir": str(output_dir),
            "segments_aligned": len(results),
            "results": results,
            "debug": debug,
            "generated_at": datetime.now(UTC).isoformat(),
        }
        write_state(root, payload)
        return payload

    # ---------------------------------------------------------
    # Internals
    # ---------------------------------------------------------
    def _resolve_project(self, path: str) -> Path:
        root = Path(path).expanduser().resolve()
        if not root.exists():
            raise RuntimeError(f"Project not found: {path}")
        return root

    def _find_postprocess_entry_for_path(self, media_entries, audio: Path):
        for e in media_entries:
            try:
                if Path(e.get("file", "")).resolve() == audio.resolve():
                    return e
            except Exception:
                pass
        return None
