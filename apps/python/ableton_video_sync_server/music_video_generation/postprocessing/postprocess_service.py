from __future__ import annotations

import json
import threading
import tempfile
import time
from datetime import datetime, UTC
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger

from .audio_utils import has_ffmpeg, extract_audio_48k, read_wav_mono, get_media_duration
from .cue_detection import gather_reference_library, compute_matches, build_segments
from .config import THRESHOLD, MIN_GAP_S, FS

MEDIA_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".m4v", ".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg"}


class PostprocessService:
    def __init__(self) -> None:
        self._jobs: Dict[str, Dict] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ helpers
    def _resolve_project(self, project_path: str) -> Path:
        root = Path(project_path or "").expanduser().resolve()
        if not root.exists() or not root.is_dir():
            raise ValueError(f"Project path not found: {project_path}")
        return root

    def _results_path(self, root: Path) -> Path:
        return root / "postprocess_matches.json"

    def _footage_dir(self, root: Path) -> Path:
        return root / "footage"

    def _reference_dir(self, root: Path) -> Path:
        candidate = root / "ableton" / "cue_refs"
        if candidate.exists():
            return candidate
        fallback = Path(__file__).resolve().parent.parent / "sound" / "cue_refs"
        return fallback

    def _load_track_map(self, root: Path) -> Dict[str, List[str]]:
        """Map cue reference file names to the track names that were armed."""
        track_map: Dict[str, List[str]] = {}
        db_path = root / "ableton_recordings_db.json"
        if not db_path.exists():
            return track_map
        try:
            payload = json.loads(db_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logger.warning("postprocess: Failed to parse %s for track metadata.", db_path)
            return track_map

        sessions = payload.get("sessions")
        if not isinstance(sessions, list):
            return track_map

        for session in sessions:
            recordings = session.get("recordings")
            if not isinstance(recordings, list):
                continue
            for recording in recordings:
                raw_tracks = recording.get("recording_track_names") or []
                if not isinstance(raw_tracks, list) or not raw_tracks:
                    continue
                names: List[str] = []
                for name in raw_tracks:
                    if isinstance(name, str):
                        cleaned = name.strip()
                        if cleaned:
                            names.append(cleaned)
                if not names:
                    continue
                for cue_key in ("start_sound_path", "end_sound_path"):
                    cue_path = recording.get(cue_key)
                    if not cue_path or not isinstance(cue_path, str):
                        continue
                    ref_name = Path(cue_path).name.lower()
                    if not ref_name:
                        continue
                    existing = track_map.setdefault(ref_name, [])
                    for entry in names:
                        if entry not in existing:
                            existing.append(entry)
        return track_map

    def _read_results(self, root: Path) -> Dict:
        path = self._results_path(root)
        if not path.exists():
            return {
                "project_path": str(root),
                "generated_at": None,
                "media": [],
                "summary": {
                    "files_processed": 0,
                    "segments_detected": 0,
                    "cue_refs_used": [],
                    "errors": [],
                },
            }
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logger.warning("postprocess: Failed to parse %s, resetting.", path)
            return {
                "project_path": str(root),
                "generated_at": None,
                "media": [],
                "summary": {
                    "files_processed": 0,
                    "segments_detected": 0,
                    "cue_refs_used": [],
                    "errors": ["Failed to parse matches file."],
                },
            }

    def _write_results(self, root: Path, payload: Dict) -> None:
        path = self._results_path(root)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)

    def _iter_media(self, footage_dir: Path) -> List[Path]:
        if not footage_dir.exists():
            return []
        return [
            p.resolve()
            for p in footage_dir.rglob("*")
            if p.is_file() and p.suffix.lower() in MEDIA_EXTENSIONS
        ]

    # ------------------------------------------------------------------ public API
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

    def start(self, project_path: str, *, threshold: float | None = None, min_gap_s: float | None = None) -> Dict:
        root = self._resolve_project(project_path)
        key = str(root)
        params = self._normalize_params(threshold=threshold, min_gap_s=min_gap_s)
        with self._lock:
            job = self._jobs.get(key)
            if job and job.get("status") == "running":
                raise ValueError("Postprocess already running for this project.")
            job = {
                "status": "running",
                "started_at": datetime.now(UTC).isoformat(),
                "completed_at": None,
                "progress": {"processed": 0, "total": 0},
                "error": None,
                "params": params,
            }
            self._jobs[key] = job
            thread = threading.Thread(target=self._worker, args=(root, key, params), daemon=True)
            thread.start()
        return job

    def state(self, project_path: str) -> Dict:
        root = self._resolve_project(project_path)
        key = str(root)
        with self._lock:
            job = self._jobs.get(key)
            job_copy = dict(job) if job else None
        results = self._read_results(root)
        return {
            "project_path": str(root),
            "job": job_copy,
            "results": results,
        }

    # ------------------------------------------------------------------ worker
    def _worker(self, root: Path, job_key: str, params: Dict[str, float]) -> None:
        job = self._jobs[job_key]
        try:
            media = self._process_project(root, job, params)
            payload = self._build_payload(root, media, params)
            self._write_results(root, payload)
            job["status"] = "completed"
            job["completed_at"] = datetime.now(UTC).isoformat()
        except Exception as exc:
            logger.exception("postprocess: job failed for %s", root)
            job["status"] = "failed"
            job["error"] = str(exc)
            job["completed_at"] = datetime.now(UTC).isoformat()

    def _process_project(self, root: Path, job: Dict, params: Dict[str, float]) -> List[Dict]:
        if not has_ffmpeg():
            raise RuntimeError("ffmpeg not found on PATH. Install ffmpeg to run postprocess.")

        footage_dir = self._footage_dir(root)
        media_files = self._iter_media(footage_dir)
        if not media_files:
            raise RuntimeError(f"No media files found in {footage_dir}")

        refs_dir = self._reference_dir(root)
        refs = gather_reference_library(refs_dir)
        track_map = self._load_track_map(root)

        media_results: List[Dict] = []
        job["progress"] = {"processed": 0, "total": len(media_files)}

        for index, file_path in enumerate(media_files, start=1):
            job["progress"]["processed"] = index - 1
            try:
                media_results.append(self._process_file(file_path, refs, root, params, track_map))
            except Exception as exc:
                logger.warning("postprocess: failed to process %s: %s", file_path, exc)
                media_results.append(
                    {
                        "file": str(file_path),
                        "relative_path": str(file_path.relative_to(root)),
                        "duration_s": None,
                        "segments": [],
                        "cue_refs_used": [],
                        "start_hits": [],
                        "end_hits": [],
                        "notes": [f"error: {exc}"],
                        "media_type": file_path.suffix.lower(),
                        "top_score": None,
                        "track_names": [],
                    }
                )
            job["progress"]["processed"] = index

        return media_results

    def _process_file(
        self,
        file_path: Path,
        refs,
        project_root: Path,
        params: Dict[str, float],
        track_map: Dict[str, List[str]],
    ) -> Dict:
        t0 = time.perf_counter()
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td) / "audio.wav"
            extract_audio_48k(str(file_path), tmp)
            rec, _fs = read_wav_mono(tmp)
        duration = get_media_duration(str(file_path)) or len(rec) / FS
        matches = compute_matches(rec, refs, params["threshold"], params["min_gap_s"])

        def _attach_tracks(hit_list: List[Dict]) -> None:
            for hit in hit_list:
                ref_id = str(hit.get("ref_id") or "")
                ref_key = Path(ref_id).name.lower()
                if not ref_key:
                    continue
                tracks = track_map.get(ref_key)
                if tracks:
                    hit["track_names"] = list(tracks)

        _attach_tracks(matches["start"])
        _attach_tracks(matches["end"])
        segments = build_segments(matches["start"], matches["end"], duration)
        cue_refs = sorted({hit["ref_id"] for hit in matches["start"] + matches["end"]})
        track_names = sorted({name for hit in matches["start"] + matches["end"] for name in hit.get("track_names", [])})
        top_score = None
        all_scores = [hit["score"] for hit in matches["start"] + matches["end"] if "score" in hit]
        if all_scores:
            top_score = max(all_scores)

        rel_path = file_path
        try:
            rel_path = file_path.relative_to(project_root)
        except ValueError:
            pass

        return {
            "file": str(file_path),
            "relative_path": str(rel_path).replace("\\", "/"),
            "duration_s": duration,
            "segments": segments,
            "cue_refs_used": cue_refs,
            "start_hits": matches["start"],
            "end_hits": matches["end"],
            "notes": [],
            "media_type": file_path.suffix.lower().lstrip("."),
            "top_score": top_score,
            "elapsed_s": time.perf_counter() - t0,
            "track_names": track_names,
        }

    def _build_payload(self, root: Path, media: List[Dict], params: Dict[str, float]) -> Dict:
        summary = {
            "files_processed": len(media),
            "segments_detected": sum(len(item.get("segments") or []) for item in media),
            "cue_refs_used": sorted({ref for item in media for ref in item.get("cue_refs_used") or []}),
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


__all__ = ["PostprocessService"]
