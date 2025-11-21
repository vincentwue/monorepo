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
from .alignment_core import compute_segment_alignment, SegmentAlignment  # <- shared math

VIDEO_EXTS = (".mp4", ".mkv", ".mov", ".ts", ".mts", ".m4v", ".avi", ".webm")
AUDIO_EXTS = (".wav", ".mp3", ".m4a", ".aac")


class FootageAlignService:
    # ---------------------------------------------------------
    # Public API
    # ---------------------------------------------------------
    def align(self, project_path: str, *, audio_path: Optional[str] = None) -> Dict:
        root = self._resolve_project(project_path)

        # 1) pick / resolve master audio
        audio = resolve_audio(root, audio_path)
        audio_dur = probe_duration(audio)

        # 2) load postprocess (cues for audio + video) and recordings
        post = load_postprocess(root)
        media_entries = post.get("media") or []

        recordings = load_recordings(root)

        # 3) find audio cue in the chosen master audio file
        audio_entry = self._find_postprocess_entry_for_path(media_entries, audio)
        if not audio_entry:
            raise RuntimeError("Audio not part of postprocess—run postprocess again.")

        audio_cue = find_start_cue(audio_entry)
        if audio_cue is None:
            raise RuntimeError("No start cue in audio; cannot align.")

        logger.info("Aligning: audio cue at %.3fs", audio_cue)

        output_dir = root / "generated" / "aligned"
        results: List[Dict] = []
        debug: List[Dict] = []

        # -----------------------------------------------------
        # per-video / per-segment alignment
        # -----------------------------------------------------
        for entry in media_entries:
            f = entry.get("file")
            if not f:
                continue

            video = Path(f)
            if video.suffix.lower() not in VIDEO_EXTS:
                # skip audio entries etc.
                continue
            if not video.exists():
                logger.warning("Align: skipping missing video %s", video)
                continue

            segments = entry.get("segments") or []
            if not segments:
                logger.debug("Align: no segments for %s; skipping", video)
                continue

            video_dur = probe_duration(video)

            # match Ableton recording for this clip (we can refine later, per segment)
            start_hits = entry.get("start_hits", [])
            end_hits = entry.get("end_hits", [])

            # use the *first* segment for identity matching; if needed we can
            # later extend this to per-segment matching
            first_seg = segments[0]
            matched_recording = find_recording_for_segment(
                seg_start=first_seg.get("start_time_s", 0),
                seg_end=first_seg.get("end_time_s"),
                start_hits=start_hits,
                end_hits=end_hits,
                recordings=recordings,
            )

            for seg in segments:
                seg_index = int(seg.get("index") or 0)
                # must have a segment start
                try:
                    seg_start = float(seg["start_time_s"])
                except (KeyError, TypeError, ValueError):
                    logger.debug("Align: skipping segment without start_time_s in %s", video)
                    continue

                seg_end_val = seg.get("end_time_s")
                seg_end = float(seg_end_val) if isinstance(seg_end_val, (int, float)) else None

                alignment: SegmentAlignment = compute_segment_alignment(
                    seg_start=seg_start,
                    seg_end=seg_end,
                    audio_cue=audio_cue,
                    audio_duration=audio_dur,
                    video_duration=video_dur,
                )

                # available / used durations are encoded in alignment
                if alignment.used_duration < 0.25:
                    logger.debug(
                        "Align: skipping segment %d of %s (used_duration=%.3fs)",
                        seg_index,
                        video,
                        alignment.used_duration,
                    )
                    continue

                out_file = output_dir / f"{video.stem}_seg{seg_index:03d}_aligned.mp4"
                run_ffmpeg(
                    video=video,
                    audio=audio,
                    trim_start=alignment.trim_start,
                    total_duration=audio_dur,
                    pad_start=alignment.pad_start,
                    pad_end=alignment.pad_end,
                    output=out_file,
                )

                meta: Dict[str, object] = {
                    "source_video": str(video),
                    "segment_index": seg_index,
                    "segment_start_s": seg_start,
                    "segment_end_s": seg_end,
                    "segment_duration_s": (
                        (seg_end - seg_start) if seg_end is not None else max(0.0, video_dur - seg_start)
                    ),
                    "trim_start": alignment.trim_start,
                    "pad_start": alignment.pad_start,
                    "pad_end": alignment.pad_end,
                    "used_duration": alignment.used_duration,
                    "output_path": str(out_file),
                    "flags": {
                        "missing_end": bool(seg.get("edge_case") == "missing_end"),
                        "too_short": alignment.used_duration < 1.0,
                        "usable": alignment.used_duration >= 1.0,
                        "confidence": 0.0,  # can be wired from cue scores later
                    },
                }

                # attach Ableton recording metadata (if we found a match)
                if matched_recording:
                    meta["recording_id"] = matched_recording.get("id")
                    meta["track_names"] = matched_recording.get("recording_track_names", []) or []
                    meta["recording_start_sound"] = matched_recording.get("start_sound_path")
                    meta["recording_end_sound"] = matched_recording.get("end_sound_path")
                else:
                    meta["recording_id"] = None
                    meta["track_names"] = []
                    meta["recording_start_sound"] = None
                    meta["recording_end_sound"] = None

                results.append(meta)

                debug.append(
                    {
                        "file": str(video),
                        "segment_index": seg_index,
                        "video_cue": seg_start,
                        "audio_cue": audio_cue,
                        "relative_offset": alignment.relative_offset,
                        "trim_start": alignment.trim_start,
                        "pad_start": alignment.pad_start,
                        "pad_end": alignment.pad_end,
                        "video_duration": video_dur,
                        "segment_end_s": seg_end,
                        "segment_duration_s": (
                            (seg_end - seg_start) if seg_end is not None else max(0.0, video_dur - seg_start)
                        ),
                        "used_duration": alignment.used_duration,
                    }
                )

        payload: Dict[str, object] = {
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

    def state(self, project_path: str) -> Dict:
        """
        Read-only access for the UI: returns the last alignment_results.json.
        """
        root = self._resolve_project(project_path)
        return read_state(root)

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
            f = e.get("file", "")
            if not f:
                continue
            try:
                if Path(f).resolve() == audio.resolve():
                    return e
            except Exception:
                # be robust to weird paths
                continue
        return None

    def resolve_audio(
        self,
        project_root: Path,
        audio_override: Optional[Path] = None,
    ) -> Path:
        """
        New public helper:

        - If audio_override is given, just return it.
        - Otherwise, try to locate a reasonable master audio file under
          <project_root>/audio or <project_root>/footage/music.
        """
        if audio_override is not None:
            return audio_override

        root = Path(project_root)
        candidates: List[Path] = []

        audio_dir = root / "audio"
        music_dir = root / "footage" / "music"

        def collect_from_dir(d: Path) -> None:
            if not d.is_dir():
                return
            for p in sorted(d.iterdir()):
                if p.is_file() and p.suffix.lower() in AUDIO_EXTS:
                    candidates.append(p)

        collect_from_dir(audio_dir)
        collect_from_dir(music_dir)

        if not candidates:
            raise FileNotFoundError(
                f"No audio export found under {audio_dir} or {music_dir}"
            )

        # Take the first match by name; you can tweak this later
        return candidates[0]

    # --- backwards-compatibility alias for old server code ---
    def _resolve_audio(self, project_root, audio_override):
        """
        Legacy API used by server.video_gen_sync.

        Keep the signature (project_root, audio_override) so existing
        code works; delegate to resolve_audio().
        """
        root_path = Path(project_root)
        override_path = Path(audio_override) if audio_override else None
        return self.resolve_audio(root_path, override_path)
