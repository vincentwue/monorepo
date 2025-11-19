from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Dict, List

from loguru import logger

MEDIA_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".m4v", ".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg"}


def resolve_project(project_path: str) -> Path:
    root = Path(project_path or "").expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise ValueError(f"Project path not found: {project_path}")
    return root


def results_path(root: Path) -> Path:
    return root / "primary_cue_matches.json"


def footage_dir(root: Path) -> Path:
    return root / "footage"


def reference_dir(root: Path) -> Path:
    candidate = root / "ableton" / "cue_refs"
    if candidate.exists():
        return candidate
    repo_root = Path(__file__).resolve().parents[5]
    return (
        repo_root
        / "apps"
        / "python"
        / "ableton_video_sync_server"
        / "music_video_generation"
        / "sound"
        / "cue_refs"
    )


def iter_media(footage_dir: Path) -> List[Path]:
    if not footage_dir.exists():
        return []
    return [
        media.resolve()
        for media in footage_dir.rglob("*")
        if media.is_file() and media.suffix.lower() in MEDIA_EXTENSIONS
    ]


def read_results(root: Path) -> Dict:
    path = results_path(root)
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


def write_results(root: Path, payload: Dict) -> None:
    path = results_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def append_log(root: Path, message: str) -> None:
    try:
        ts = datetime.now().isoformat(timespec="seconds")
        log_path = root / "logs" / "primary_cues.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"[{ts}] {message}\n")
    except Exception as exc:
        logger.debug("primary-cues: failed to append log entry: %s", exc)


def build_payload(root: Path, media: List[Dict], params: Dict[str, float]) -> Dict:
    total_pairs = sum(len(item.get("pairs") or []) for item in media)
    missing_start = sum(
        1 for item in media for pair in item.get("pairs") or [] if pair.get("status") == "missing_start"
    )
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


__all__ = [
    "append_log",
    "build_payload",
    "footage_dir",
    "iter_media",
    "read_results",
    "reference_dir",
    "resolve_project",
    "results_path",
    "write_results",
]
