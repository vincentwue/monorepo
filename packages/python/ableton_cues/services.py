from __future__ import annotations

import json
import tempfile
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import numpy as np
from loguru import logger

from music_video_generation.postprocessing.audio_utils import (
    extract_audio_48k,
    fade,
    get_media_duration,
    has_ffmpeg,
    read_wav_mono,
)
from music_video_generation.postprocessing.config import FADE_MS, FS, MIN_GAP_S, THRESHOLD

from .detection import build_segments, compute_matches, gather_reference_library, find_all_matches, deduplicate_hits

MEDIA_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".m4v", ".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg"}


class PrimaryCueDetectionService:
    START_WINDOW_PRE_S = 0.4
    START_WINDOW_POST_S = 1.4
    END_WINDOW_PRE_S = 1.4
    END_WINDOW_POST_S = 0.4
    SECONDARY_THRESHOLD_SCALE = 0.8
    SECONDARY_MIN_GAP_S = 0.05

    def __init__(self) -> None:
        self._jobs: Dict[str, Dict] = {}
        self._lock = threading.Lock()

    def _resolve_project(self, project_path: str) -> Path:
        root = Path(project_path or "").expanduser().resolve()
        if not root.exists() or not root.is_dir():
            raise ValueError(f"Project path not found: {project_path}")
        return root

    def _results_path(self, root: Path) -> Path:
        return root / "primary_cue_matches.json"

    def _footage_dir(self, root: Path) -> Path:
        return root / "footage"

    def _reference_dir(self, root: Path) -> Path:
        candidate = root / "ableton" / "cue_refs"
        if candidate.exists():
            return candidate
        root = Path(__file__).resolve().parents[4]
        fallback = root / "apps" / "python" / "ableton_video_sync_server" / "music_video_generation" / "sound" / "cue_refs"
        return fallback

    def _iter_media(self, footage_dir: Path) -> List[Path]:
        if not footage_dir.exists():
            return []
        return [
            p.resolve()
            for p in footage_dir.rglob("*")
            if p.is_file() and p.suffix.lower() in MEDIA_EXTENSIONS
        ]

    def _read_results(self, root: Path) -> Dict:
        path = self._results_path(root)
        if not path.exists():
            return {
                "project_path": str(root),
                "generated_at": None,
                "media": [],
                "summary": {
                    "files_processed": 0,
                    "pairs_detected": 0,
                    "complete_pairs": 0,
                    "missing_start": 0,
                    "missing_end": 0,
                    "errors": [],
                },
            }
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logger.warning("primary-cues: Failed to parse %s, resetting.", path)
            return {
                "project_path": str(root),
                "generated_at": None,
                "media": [],
                "summary": {
                    "files_processed": 0,
                    "pairs_detected": 0,
                    "complete_pairs": 0,
                    "missing_start": 0,
                    "missing_end": 0,
                    "errors": ["Failed to parse matches file."],
                },
            }

    def _write_results(self, root: Path, payload: Dict) -> None:
        path = self._results_path(root)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)

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

    def _load_primary_refs(self, refs_dir: Path) -> Dict[str, List[Dict]]:
        primary = {"start": [], "end": []}
        for kind, filename in (("start", "start.wav"), ("end", "end.wav")):
            path = refs_dir / filename
            if not path.exists():
                continue
            try:
                data, _fs = read_wav_mono(path)
                primary[kind].append(
                    {
                        "id": filename,
                        "samples": fade(data.copy(), ms=FADE_MS * 2),
                    }
                )
            except Exception as exc:
                logger.warning("primary-cues: failed to load %s: %s", path, exc)
        return primary

    def _secondary_refs(self, refs_dir: Path) -> Dict[str, List[Dict]]:
        return gather_reference_library(refs_dir, include_common_prefix=False)

    def start(
        self,
        project_path: str,
        *,
        threshold: float | None = None,
        min_gap_s: float | None = None,
        files: List[str] | None = None,
    ) -> Dict:
        root = self._resolve_project(project_path)
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
            thread = threading.Thread(target=self._worker, args=(root, key, params, targets), daemon=True)
            thread.start()
        return job

    def state(self, project_path: str) -> Dict:
        root = self._resolve_project(project_path)
        key = f"primary::{root}"
        with self._lock:
            job = self._jobs.get(key)
            job_copy = dict(job) if job else None
        results = self._read_results(root)
        return {
            "project_path": str(root),
            "job": job_copy,
            "results": results,
        }

    def reset(self, project_path: str) -> Dict:
        root = self._resolve_project(project_path)
        key = f"primary::{root}"
        with self._lock:
            job = self._jobs.get(key)
            if job and job.get("status") == "running":
                raise ValueError("Cannot reset while cue detection is running.")
        results_path = self._results_path(root)
        if results_path.exists():
            results_path.unlink()
        return self.state(project_path)

    def _worker(self, root: Path, job_key: str, params: Dict[str, float], targets: Optional[set[Path]]) -> None:
        job = self._jobs[job_key]
        try:
            media = self._process_project(root, job, params, targets)
            payload = self._build_payload(root, media, params)
            self._write_results(root, payload)
            job["status"] = "completed"
            job["completed_at"] = datetime.now(UTC).isoformat()
        except Exception as exc:
            logger.exception("primary-cues: job failed for %s", root)
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

        footage_dir = self._footage_dir(root)
        media_files = self._iter_media(footage_dir)
        if not media_files:
            raise RuntimeError(f"No media files found in {footage_dir}")

        if targets:
            target_paths = {p.resolve() for p in targets}
            media_files = [p for p in media_files if p.resolve() in target_paths]
            if not media_files:
                raise RuntimeError("No matching media files found for requested subset.")

        refs_dir = self._reference_dir(root)
        primary_refs = self._load_primary_refs(refs_dir)
        secondary_refs = self._secondary_refs(refs_dir)

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
                        "notes": [f"error: {exc}"],
                    }
                )
            job["progress"]["processed"] = index

        return media_results

    def _process_file(
        self,
        file_path: Path,
        project_root: Path,
        primary_refs: Dict[str, List[Dict]],
        secondary_refs: Dict[str, List[Dict]],
        params: Dict[str, float],
    ) -> Dict:
        t0 = time.perf_counter()
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td) / "audio.wav"
            extract_audio_48k(str(file_path), tmp)
            rec, _fs = read_wav_mono(tmp)
        duration = get_media_duration(str(file_path)) or len(rec) / FS
        matches = compute_matches(rec, primary_refs, params["threshold"], params["min_gap_s"])
        start_hits = matches.get("start", [])
        end_hits = matches.get("end", [])
        segments = build_segments(start_hits, end_hits, duration)
        start_pairs = self._find_secondary_matches(rec, secondary_refs.get("start") or [], start_hits, is_start=True, params=params)
        end_pairs = self._find_secondary_matches(rec, secondary_refs.get("end") or [], end_hits, is_start=False, params=params)
        pairs = self._build_pairs(segments, start_hits, end_hits, start_pairs, end_pairs)

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

    def _scan_window(
        self,
        rec: np.ndarray,
        refs: Sequence[Dict],
        anchor_time: float | None,
        window_pre: float,
        window_post: float,
        threshold: float,
    ) -> List[Dict]:
        if anchor_time is None or not refs:
            return []
        start_t = max(0.0, anchor_time - window_pre)
        end_t = min(len(rec) / FS, anchor_time + window_post)
        if end_t <= start_t:
            return []
        start_idx = int(start_t * FS)
        end_idx = int(end_t * FS)
        segment = rec[start_idx:end_idx]
        if len(segment) == 0:
            return []
        hits: List[Dict] = []
        for ref in refs:
            raw_hits = find_all_matches(ref["samples"], segment, threshold, self.SECONDARY_MIN_GAP_S)
            for idx, score in raw_hits:
                hits.append(
                    {
                        "time_s": (start_idx + idx) / FS,
                        "score": score,
                        "ref_id": ref.get("id", ""),
                    }
                )
        hits = deduplicate_hits(hits, tol_s=0.1)
        hits.sort(key=lambda h: h["score"], reverse=True)
        return hits

    def _find_secondary_matches(
        self,
        rec: np.ndarray,
        refs: Sequence[Dict],
        anchors: Sequence[Dict],
        *,
        is_start: bool,
        params: Dict[str, float],
    ) -> List[List[Dict]]:
        window_pre = self.START_WINDOW_PRE_S if is_start else self.END_WINDOW_PRE_S
        window_post = self.START_WINDOW_POST_S if is_start else self.END_WINDOW_POST_S
        secondary_threshold = max(0.05, params["threshold"] * self.SECONDARY_THRESHOLD_SCALE)
        buckets: List[List[Dict]] = []
        for anchor in anchors:
            hits = self._scan_window(rec, refs, anchor.get("time_s"), window_pre, window_post, secondary_threshold)
            buckets.append(hits)
        return buckets

    def _build_pairs(
        self,
        segments: List[Dict],
        start_hits: List[Dict],
        end_hits: List[Dict],
        start_secondary: List[List[Dict]],
        end_secondary: List[List[Dict]],
    ) -> List[Dict]:
        pairs: List[Dict] = []
        end_index = 0
        for idx, segment in enumerate(segments, start=1):
            start_anchor = start_hits[idx - 1] if idx - 1 < len(start_hits) else None
            end_anchor = None
            if segment.get("end_time_s") is not None:
                while end_index < len(end_hits):
                    candidate = end_hits[end_index]
                    end_index += 1
                    if candidate.get("time_s", 0.0) >= segment["start_time_s"]:
                        end_anchor = candidate
                        break
            start_sec_hits = start_secondary[idx - 1] if idx - 1 < len(start_secondary) else []
            if end_anchor is not None and 0 <= (end_index - 1) < len(end_secondary):
                end_sec_hits = end_secondary[end_index - 1]
            else:
                end_sec_hits = []
            status = "complete"
            if start_anchor is None:
                status = "missing_start"
            elif end_anchor is None:
                status = "missing_end"
            pairs.append(
                {
                    "index": idx,
                    "start_anchor": start_anchor,
                    "start_secondary_hits": start_sec_hits,
                    "end_anchor": end_anchor,
                    "end_secondary_hits": end_sec_hits,
                    "status": status,
                    "window_start_s": segment["start_time_s"],
                    "window_end_s": segment.get("end_time_s"),
                }
            )
        return pairs

    def _build_payload(self, root: Path, media: List[Dict], params: Dict[str, float]) -> Dict:
        total_pairs = sum(len(item.get("pairs") or []) for item in media)
        missing_start = sum(1 for item in media for pair in item.get("pairs") or [] if pair.get("status") == "missing_start")
        missing_end = sum(1 for item in media for pair in item.get("pairs") or [] if pair.get("status") == "missing_end")
        complete = sum(1 for item in media for pair in item.get("pairs") or [] if pair.get("status") == "complete")
        summary = {
            "files_processed": len(media),
            "pairs_detected": total_pairs,
            "complete_pairs": complete,
            "missing_start": missing_start,
            "missing_end": missing_end,
            "errors": [
                note
                for item in media
                for note in item.get("notes") or []
                if note.lower().startswith("error")
            ],
        }
        return {
            "project_path": str(root),
            "generated_at": datetime.now(UTC).isoformat(),
            "media": media,
            "summary": summary,
            "settings": params,
        }


__all__ = ["PrimaryCueDetectionService"]
