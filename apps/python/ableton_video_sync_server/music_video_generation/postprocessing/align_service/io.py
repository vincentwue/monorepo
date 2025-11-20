from __future__ import annotations

import json
from json import JSONDecodeError
from pathlib import Path
from typing import Dict, List

from loguru import logger


# ---------------------------------------------------------------------------
# State file (alignment_results.json)
# ---------------------------------------------------------------------------

def _state_path(root: Path) -> Path:
    return root / "generated" / "aligned" / "alignment_results.json"


def read_state(root: Path) -> Dict:
    path = _state_path(root)
    if not path.exists():
        return {
            "project_path": str(root),
            "audio_path": None,
            "audio_duration": None,
            "output_dir": str((root / "generated" / "aligned").resolve()),
            "segments_aligned": 0,
            "results": [],
            "debug": [],
        }
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except JSONDecodeError:
        logger.warning("align_service: failed to parse %s, resetting state.", path)
        return {
            "project_path": str(root),
            "audio_path": None,
            "audio_duration": None,
            "output_dir": str((root / "generated" / "aligned").resolve()),
            "segments_aligned": 0,
            "results": [],
            "debug": [],
        }

    data.setdefault("project_path", str(root))
    data.setdefault("output_dir", str((root / "generated" / "aligned").resolve()))
    data.setdefault("segments_aligned", len(data.get("results") or []))
    data.setdefault("debug", [])
    return data


def write_state(root: Path, payload: Dict) -> None:
    path = _state_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


# ---------------------------------------------------------------------------
# Postprocess results (postprocess_matches.json)
# ---------------------------------------------------------------------------

def load_postprocess(root: Path) -> Dict:
    """
    Load postprocess_matches.json (cue positions for audio+video).
    """
    path = root / "postprocess_matches.json"
    if not path.exists():
        raise RuntimeError("postprocess_matches.json not found. Run postprocess first.")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except JSONDecodeError as exc:
        raise RuntimeError(f"Failed to parse {path}: {exc}") from exc


# ---------------------------------------------------------------------------
# Ableton recordings metadata (recordings.json / ableton_recordings_db.json)
# ---------------------------------------------------------------------------

def load_recordings(root: Path) -> List[Dict]:
    """
    Load Ableton recordings metadata.

    Supported formats:

    1) Current format (recordings.json):

        {
          "cues_enabled": true,
          "capture_enabled": true,
          "cue_active": false,
          "recordings": [ { ... }, ... ],
          "last_updated": "..."
        }

    2) Flat list in recordings.json:

        [ { ... }, { ... } ]

    3) Legacy ableton_recordings_db.json:

        {
          "sessions": [
            {
              "recordings": [ { ... }, ... ]
            },
            ...
          ]
        }
    """
    primary = root / "recordings.json"
    legacy_db = root / "ableton_recordings_db.json"

    # Preferred: recordings.json
    if primary.exists():
        try:
            raw = json.loads(primary.read_text(encoding="utf-8"))
        except JSONDecodeError:
            logger.warning("align_service: failed to parse %s", primary)
        else:
            # case 1: dict with "recordings"
            if isinstance(raw, dict) and isinstance(raw.get("recordings"), list):
                return list(raw["recordings"])
            # case 2: plain list
            if isinstance(raw, list):
                return list(raw)

            logger.warning(
                "align_service: recordings.json has unexpected shape, falling back to legacy loader."
            )

    # Fallback: legacy ableton_recordings_db.json
    if legacy_db.exists():
        try:
            raw = json.loads(legacy_db.read_text(encoding="utf-8"))
        except JSONDecodeError:
            logger.warning("align_service: failed to parse %s", legacy_db)
        else:
            recs: List[Dict] = []
            sessions = raw.get("sessions")
            if isinstance(sessions, list):
                for session in sessions:
                    items = session.get("recordings")
                    if isinstance(items, list):
                        recs.extend(items)
            if recs:
                return recs

    logger.warning(
        "align_service: no usable recordings metadata found "
        "(no recordings.json / ableton_recordings_db.json)."
    )
    return []
