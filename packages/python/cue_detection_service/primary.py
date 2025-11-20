from __future__ import annotations

import tempfile
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger

from music_video_generation.postprocessing.audio_utils import (
    extract_audio_48k,
    get_media_duration,
    has_ffmpeg,
    read_wav_mono,
)
from music_video_generation.postprocessing.config import FS, MIN_GAP_S, THRESHOLD

try:
    from cue_detection import build_segments, compute_matches
except ImportError:  # pragma: no cover - workspace fallback
    from packages.python.cue_detection import build_segments, compute_matches

from . import matching, project, references


AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg"}


class PrimaryCueDetectionService:
    SECONDARY_THRESHOLD_SCALE = 0.8
    SECONDARY_MIN_GAP_S = 0.05

    def __init__(self) -> None:
        self._jobs: Dict[str, Dict] = {}
        self._lock = threading.Lock()
        self._matcher = matching.SecondaryMatcher(min_gap_s=self.SECONDARY_MIN_GAP_S)

    def _normalize_params(
        self,
        *,
        threshold: Optional[float],
        min_gap_s: Optional[float],
    ) -> Dict[str, float]:
        thr = THRESHOLD if threshold is None else float(threshold)
        gap = MIN_GAP_S if min_gap_s is None else float(min_gap_s)
        thr = min(max(thr, 0.0), 1.0)
        gap = max(gap, 0.0)
        return {"threshold": thr, "min_gap_s": gap}

    def start(
        self,
        project_path: str,
        *,
        threshold: float | None = None,
        min_gap_s: float | None = None,
        files: List[str] | None = None,
    ) -> Dict:
        root = project.resolve_project(project_path)
        key = f"primary::{root}"
        params = self._normalize_params(threshold=threshold, min_gap_s=min_gap_s)

        targets = None
        if files:
            targets = {Path(f).expanduser().resolve() for f in files if f}

        with self._lock:
            job = self._jobs.get(key)
            if job and job.get("status") == "running":
                raise ValueError("Primary cue detection already running for this project.")

            job = {
                "status": "running",
                "started_at": datetime.now(UTC).isoformat(),
                "completed_at": None,
                "progress": {"processed": 0, "total": 0},
                "error": None,
                "params": params,
            }
            if targets:
                job["targets"] = [str(p) for p in targets]
            self._jobs[key] = job

            project.append_log(
                root,
                "Primary cue detection started (threshold=%.2f gap=%.2f targets=%s)"
                % (
                    params["threshold"],
                    params["min_gap_s"],
                    ",".join(str(p) for p in targets) if targets else "all",
                ),
            )

            threading.Thread(
                target=self._worker,
                args=(root, key, params, targets),
                daemon=True,
            ).start()

        return job

    def state(self, project_path: str) -> Dict:
        root = project.resolve_project(project_path)
        key = f"primary::{root}"
        with self._lock:
            job = self._jobs.get(key)
            job_copy = dict(job) if job else None
        results = project.read_results(root)
        return {
            "project_path": str(root),
            "job": job_copy,
            "results": results,
        }

    def reset(self, project_path: str) -> Dict:
        root = project.resolve_project(project_path)
        key = f"primary::{root}"
        with self._lock:
            job = self._jobs.get(key)
            if job and job.get("status") == "running":
                raise ValueError("Cannot reset while cue detection is running.")
        results_path = project.results_path(root)
        if results_path.exists():
            results_path.unlink()
        return self.state(project_path)

    # ------------------------------------------------------------------
    # Worker
    # ------------------------------------------------------------------

    def _worker(
        self,
        root: Path,
        job_key: str,
        params: Dict[str, float],
        targets: Optional[set[Path]],
    ) -> None:
        job = self._jobs[job_key]
        try:
            media = self._process_project(root, job, params, targets)
            payload = project.build_payload(root, media, params)
            project.write_results(root, payload)
            project.append_log(root, "Primary cue detection finished successfully.")
            job["status"] = "completed"
            job["completed_at"] = datetime.now(UTC).isoformat()
        except Exception as exc:
            logger.exception("primary-cues: job failed for %s", root)
            project.append_log(root, f"Primary cue detection failed: {exc}")
            job["status"] = "failed"
            job["error"] = str(exc)
            job["completed_at"] = datetime.now(UTC).isoformat()

    def _process_project(
        self,
        root: Path,
        job: Dict,
        params: Dict[str, float],
        targets: Optional[set[Path]],
    ) -> List[Dict]:
        if not has_ffmpeg():
            raise RuntimeError("ffmpeg not found on PATH. Install ffmpeg to run cue detection.")

        footage_dir = project.footage_dir(root)
        media_files = project.iter_media(footage_dir)
        if not media_files:
            raise RuntimeError(f"No media files found in {footage_dir}")

        if targets:
            target_paths = {p.resolve() for p in targets}
            media_files = [p for p in media_files if p.resolve() in target_paths]
            if not media_files:
                raise RuntimeError("No matching media files found for requested subset.")

        refs_dir = project.reference_dir(root)
        primary_refs = references.load_primary_refs(refs_dir)
        secondary_refs = references.load_secondary_refs(refs_dir)

        project.append_log(
            root,
            "Prepared %d primary start refs, %d end refs (threshold=%.2f gap=%.2f)"
            % (
                len(primary_refs["start"]),
                len(primary_refs["end"]),
                params["threshold"],
                params["min_gap_s"],
            ),
        )

        media_results: List[Dict] = []
        job["progress"] = {"processed": 0, "total": len(media_files)}

        for index, file_path in enumerate(media_files, start=1):
            job["progress"]["processed"] = index - 1
            try:
                media_results.append(
                    self._process_file(file_path, root, primary_refs, secondary_refs, params)
                )
            except Exception as exc:
                logger.warning("primary-cues: failed to process %s: %s", file_path, exc)
                media_results.append(
                    {
                        "file": str(file_path),
                        "relative_path": str(file_path.relative_to(root)),
                        "duration_s": None,
                        "pairs": [],
                        "start_hits": [],
                        "end_hits": [],
                        "elapsed_s": 0.0,
                        "notes": [f"error: {exc}"],
                    }
                )
            job["progress"]["processed"] = index

        return media_results

    # ------------------------------------------------------------------
    # Single file
    # ------------------------------------------------------------------

    def _process_file(
        self,
        file_path: Path,
        project_root: Path,
        primary_refs: Dict[str, List[Dict]],
        secondary_refs: Dict[str, List[Dict]],
        params: Dict[str, float],
    ) -> Dict:
        """
        Process one media file:
          - Extract mono 48k audio.
          - Run primary cue matching.
          - Build segments.
          - Run secondary matching.
          - Build final pairs.

        IMPORTANT: for *video* files we strip generic fallback 'end.wav'
        from end hits. This prevents 'end.wav' from hijacking camera
        segments – it remains allowed only for audio exports (mp3/wav).
        """
        t0 = time.perf_counter()

        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td) / "audio.wav"
            extract_audio_48k(str(file_path), tmp)
            rec, _fs = read_wav_mono(tmp)

        duration = get_media_duration(str(file_path)) or len(rec) / FS
        matches = compute_matches(rec, primary_refs, params["threshold"], params["min_gap_s"])

        start_hits = matches.get("start", []) or []
        raw_end_hits = matches.get("end", []) or []

        suffix = file_path.suffix.lower()
        is_audio = suffix in AUDIO_EXTENSIONS

        if is_audio:
            end_hits = raw_end_hits
        else:
            # VIDEO: drop generic fallback end cues (e.g. 'end.wav')
            end_hits = [h for h in raw_end_hits if not matching._is_fallback_end(h)]
            if raw_end_hits and not end_hits:
                logger.info(
                    "primary-cues: %s had only fallback end hits (%d), "
                    "dropping them for video segments.",
                    file_path.name,
                    len(raw_end_hits),
                )

        segments = build_segments(start_hits, end_hits, duration)

        secondary_threshold = max(0.05, params["threshold"] * self.SECONDARY_THRESHOLD_SCALE)

        start_pairs = self._matcher.find_secondary_matches(
            rec,
            secondary_refs.get("start") or [],
            start_hits,
            threshold=secondary_threshold,
            is_start=True,
        )
        end_pairs = self._matcher.find_secondary_matches(
            rec,
            secondary_refs.get("end") or [],
            end_hits,
            threshold=secondary_threshold,
            is_start=False,
        )

        pairs = matching.build_pairs(segments, start_hits, end_hits, start_pairs, end_pairs)

        max_start_score = max((hit.get("score", 0.0) for hit in start_hits), default=0.0)
        max_end_score = max((hit.get("score", 0.0) for hit in end_hits), default=0.0)

        logger.info(
            "primary-cues: %s start_hits=%d (max=%.3f) end_hits=%d (max=%.3f) [audio=%s]",
            file_path.name,
            len(start_hits),
            max_start_score,
            len(end_hits),
            max_end_score,
            is_audio,
        )

        project.append_log(
            project_root,
            "%s start_hits=%d (max=%.3f) end_hits=%d (max=%.3f) [audio=%s]"
            % (file_path.name, len(start_hits), max_start_score, len(end_hits), max_end_score, is_audio),
        )

        rel_path = file_path
        try:
            rel_path = file_path.relative_to(project_root)
        except ValueError:
            pass

        return {
            "file": str(file_path),
            "relative_path": str(rel_path).replace("\\", "/"),
            "duration_s": duration,
            "pairs": pairs,
            "start_hits": start_hits,
            "end_hits": end_hits,
            "elapsed_s": time.perf_counter() - t0,
            "notes": [],
        }


__all__ = ["PrimaryCueDetectionService"]
