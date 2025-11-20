from __future__ import annotations

import json
import math
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger


class FootageAlignService:
    """Aligns all footage clips to the master audio length."""

    AUDIO_EXTS = (".wav", ".mp3", ".m4a", ".aac", ".flac", ".aiff")
    VIDEO_EXTS = (".mp4", ".mkv", ".mov", ".ts", ".mts", ".m4v", ".avi", ".webm")
    MAX_ABSOLUTE_OFFSET_S = 30.0

    def _resolve_project(self, project_path: str) -> Path:
        root = Path(project_path or "").expanduser().resolve()
        if not root.exists() or not root.is_dir():
            raise ValueError(f"Project path not found: {project_path}")
        return root

    def _state_file(self, root: Path) -> Path:
        return root / "generated" / "aligned" / "alignment_results.json"

    def _write_state(self, root: Path, payload: Dict[str, object]) -> None:
        path = self._state_file(root)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)

    def _read_state(self, root: Path) -> Dict[str, object]:
        path = self._state_file(root)
        if not path.exists():
            return {
                "project_path": str(root),
                "output_dir": str((root / "generated" / "aligned").resolve()),
                "results": [],
                "videos_processed": 0,
                "audio_path": None,
                "audio_duration": None,
                "debug": [],
            }
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            data.setdefault("project_path", str(root))
            data.setdefault("output_dir", str((root / "generated" / "aligned").resolve()))
            return data
        except json.JSONDecodeError:
            logger.warning("align_service: failed to parse %s", path)
            return {
                "project_path": str(root),
                "output_dir": str((root / "generated" / "aligned").resolve()),
                "results": [],
                "videos_processed": 0,
                "audio_path": None,
                "audio_duration": None,
                "debug": [],
            }

    def _resolve_audio(self, root: Path, override: Optional[str]) -> Path:
        if override:
            audio = Path(override).expanduser().resolve()
            if not audio.exists():
                raise ValueError(f"Audio file not found: {override}")
            return audio

        music_dir = root / "footage" / "music"
        candidates: List[Path] = []
        if music_dir.exists():
            candidates.extend(sorted(p for p in music_dir.iterdir() if p.suffix.lower() in self.AUDIO_EXTS))
        if not candidates:
            candidates.extend(sorted(p for p in root.glob("*") if p.suffix.lower() in self.AUDIO_EXTS))
        if not candidates:
            raise ValueError("No audio files found in project. Provide audio_path explicitly.")
        return candidates[0]

    def _probe_duration(self, path: Path) -> float:
        try:
            cmd = [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ]
            out = subprocess.check_output(cmd, text=True).strip()
            return float(out)
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(f"ffprobe failed for {path}: {exc}") from exc
        except ValueError as exc:
            raise RuntimeError(f"Unable to parse duration for {path}: {exc}") from exc

    def _load_postprocess_results(self, root: Path) -> Dict:
        path = root / "postprocess_matches.json"
        if not path.exists():
            raise ValueError("postprocess_matches.json not found. Run postprocess first.")
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Failed to parse {path}: {exc}") from exc

    def _load_recordings_db(self, root: Path) -> Dict[str, Dict]:
        db_path = root / "ableton_recordings_db.json"
        if not db_path.exists():
            return {}
        try:
            payload = json.loads(db_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logger.warning("align_service: failed to parse %s", db_path)
            return {}

        mapping: Dict[str, Dict] = {}
        sessions = payload.get("sessions")
        if not isinstance(sessions, list):
            return mapping
        for session in sessions:
            recordings = session.get("recordings")
            if not isinstance(recordings, list):
                continue
            for rec in recordings:
                start_path = rec.get("start_sound_path")
                if isinstance(start_path, str) and start_path:
                    mapping[Path(start_path).name.lower()] = rec
                end_path = rec.get("end_sound_path")
                if isinstance(end_path, str) and end_path:
                    mapping[Path(end_path).name.lower()] = rec
        return mapping

    def _find_start_offset(self, entry: Dict) -> Optional[float]:
        hits = entry.get("start_hits") or []
        for hit in hits:
            time_s = hit.get("time_s")
            if isinstance(time_s, (int, float)):
                return float(time_s)
        segments = entry.get("segments") or []
        if segments:
            time_s = segments[0].get("start_time_s")
            if isinstance(time_s, (int, float)):
                return float(time_s)
        return None

    def _resolve_absolute_cue(self, cue_id: str, recordings: Dict[str, Dict]) -> Optional[float]:
        rec = recordings.get(cue_id.lower())
        if not rec:
            return None
        ts = rec.get("time_start_recording")
        if isinstance(ts, (int, float)):
            return float(ts)
        return None

    def _iter_video_cue_candidates(
        self,
        entry: Dict,
        recordings: Dict[str, Dict],
    ) -> List[Dict[str, Optional[float] | str]]:
        """
        For a given media entry (one video file), return one candidate per
        distinct cue / recording that appears in start_hits.

        Each candidate is:
          {
            "cue_id": <ref_id or None>,
            "cue_offset": <time_s>,
            "abs_offset": <absolute recording start> or None,
          }

        If no suitable hits are found, fall back to a single candidate
        using _find_start_offset (old behaviour).
        """
        hits = entry.get("start_hits") or []
        by_id: Dict[str, Dict[str, Optional[float] | str]] = {}

        for hit in hits:
            ref_id = hit.get("ref_id")
            if not isinstance(ref_id, str):
                continue
            time_s = hit.get("time_s")
            if not isinstance(time_s, (int, float)):
                continue

            # Map ref_id → recording via recordings DB
            abs_offset = self._resolve_absolute_cue(ref_id, recordings)
            # Only treat it as a "take" if we can map it to a recording
            if abs_offset is None:
                continue

            # Only keep first hit per cue_id (additional hits are usually noise or echoes)
            if ref_id not in by_id:
                by_id[ref_id] = {
                    "cue_id": ref_id,
                    "cue_offset": float(time_s),
                    "abs_offset": float(abs_offset),
                }

        if by_id:
            return list(by_id.values())

        # Fallback: old behaviour (single start offset, no recording linkage)
        offset = self._find_start_offset(entry)
        if offset is None:
            return []
        return [
            {
                "cue_id": "",
                "cue_offset": float(offset),
                "abs_offset": None,
            }
        ]

    def _run_ffmpeg(
        self,
        video: Path,
        audio: Path,
        trim_start: float,
        total_duration: float,
        pad_start: float,
        pad_end: float,
        output: Path,
    ) -> None:
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

        logger.info("Aligning %s -> %s", video, output)
        subprocess.run(cmd, check=True)

    def align(self, project_path: str, *, audio_path: Optional[str] = None) -> Dict[str, object]:
        root = self._resolve_project(project_path)
        audio = self._resolve_audio(root, audio_path)
        audio_dur = self._probe_duration(audio)
        if audio_dur <= 0:
            raise RuntimeError("Audio duration is zero.")

        data = self._load_postprocess_results(root)
        media_entries = data.get("media") or []
        recordings = self._load_recordings_db(root)

        # --- establish reference cue on the audio file ----------------------
        audio_entry_offset = 0.0
        audio_abs: Optional[float] = None
        for entry in media_entries:
            entry_path = entry.get("file")
            if not entry_path:
                continue
            try:
                if Path(entry_path).resolve() == audio.resolve():
                    hits = entry.get("start_hits") or []
                    if hits:
                        cue_id = hits[0].get("ref_id")
                        if isinstance(cue_id, str):
                            audio_abs = self._resolve_absolute_cue(cue_id, recordings)
                    rel = self._find_start_offset(entry)
                    if rel is not None:
                        audio_entry_offset = rel
                    break
            except Exception:
                continue
        if audio_abs is None:
            audio_abs = 0.0
        logger.info("Align: audio reference offset %.3fs absolute %.3fs", audio_entry_offset, audio_abs)

        # --- align each video; potentially multiple takes per file ---------
        output_dir = root / "generated" / "aligned"
        outputs: List[Dict[str, object]] = []
        debug_rows: List[Dict[str, float | str]] = []

        for entry in media_entries:
            video_path = entry.get("file")
            if not video_path:
                continue
            video = Path(video_path)
            if video.suffix.lower() not in self.VIDEO_EXTS:
                logger.debug("Skipping non-video media %s", video)
                continue
            if not video.exists():
                logger.warning("Skipping missing video %s", video)
                continue

            # one candidate per distinct cue / recording on this clip
            candidates = self._iter_video_cue_candidates(entry, recordings)
            if not candidates:
                logger.warning("Skipping %s (no usable start cue detected)", video)
                continue

            # probe duration once per file
            video_dur = self._probe_duration(video)

            for idx, cand in enumerate(candidates, start=1):
                cue_offset = float(cand["cue_offset"])  # type: ignore[arg-type]
                abs_offset = cand.get("abs_offset")
                if isinstance(abs_offset, (int, float)):
                    abs_offset = float(abs_offset)
                else:
                    abs_offset = None

                absolute_component = 0.0
                if abs_offset is not None and audio_abs is not None:
                    delta = abs_offset - audio_abs
                    if abs(delta) <= self.MAX_ABSOLUTE_OFFSET_S:
                        absolute_component = delta
                    else:
                        logger.debug(
                            "Align: ignoring absolute offset delta %.3fs for %s (beyond max %.1fs)",
                            delta,
                            video,
                            self.MAX_ABSOLUTE_OFFSET_S,
                        )

                relative_component = cue_offset - audio_entry_offset
                combined_offset = absolute_component + relative_component
                trim_start = max(0.0, combined_offset)
                pad_start = max(0.0, -combined_offset)
                available = max(0.0, video_dur - trim_start)
                if available <= 0.1:
                    logger.warning("Skipping %s (no usable duration after trimming) [take %d]", video, idx)
                    continue
                usable_audio = max(0.0, audio_dur - pad_start)
                used_duration = min(usable_audio, available)
                if used_duration <= 0.1:
                    logger.warning("Skipping %s (insufficient usable duration) [take %d]", video, idx)
                    continue
                pad_end = max(0.0, audio_dur - pad_start - used_duration)

                # distinguish multiple takes from same source file
                suffix = f"_take{idx}" if len(candidates) > 1 else ""
                target = output_dir / f"{video.stem}{suffix}_aligned.mp4"

                self._run_ffmpeg(video, audio, trim_start, audio_dur, pad_start, pad_end, target)

                outputs.append(
                    {
                        "source": str(video),
                        "output": str(target),
                        "trim_start": trim_start,
                        "pad_start": pad_start,
                        "pad_end": pad_end,
                        "used_duration": used_duration,
                    }
                )
                debug_rows.append(
                    {
                        # make file label unique per take for the UI/debug table
                        "file": f"{video} (take {idx})" if len(candidates) > 1 else str(video),
                        "video_cue": cue_offset,
                        "audio_cue": audio_entry_offset,
                        "video_abs": abs_offset,
                        "audio_abs": audio_abs,
                        "relative_offset": combined_offset,
                        "absolute_component": absolute_component,
                        "relative_component": relative_component,
                        "trim_start": trim_start,
                        "pad_start": pad_start,
                        "pad_end": pad_end,
                        "video_duration": video_dur,
                    }
                )

        payload = {
            "project_path": str(root),
            "audio_path": str(audio),
            "audio_duration": audio_dur,
            "output_dir": str(output_dir),
            "videos_processed": len(outputs),
            "results": outputs,
            "debug": debug_rows,
            "generated_at": datetime.now(UTC).isoformat(),
        }
        self._write_state(root, payload)
        return payload

    def state(self, project_path: str) -> Dict[str, object]:
        root = self._resolve_project(project_path)
        return self._read_state(root)


__all__ = ["FootageAlignService"]
