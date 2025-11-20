#!/usr/bin/env python3
"""
Ableton Export Matcher (file-based)
-----------------------------------
Detects cue tones in an Ableton render (MP3/WAV),
matches them to a recording from recordings.json.
"""

import sys
from pathlib import Path
from typing import Dict, Optional

import numpy as np

from .project_files import ProjectFiles, make_store

# ... keep your existing cue detection imports and gather_all_cues()

# (leave detect_audio_start_cue as you have it, unchanged)


def find_ableton_recording_for_export(
    store: ProjectFiles,
    ref_id: str,
) -> Optional[Dict[str, object]]:
    rec = store.find_recording_by_cue(ref_id)
    if not rec:
        print(f"[warn] No recording found for cue {ref_id}")
        return None

    print(
        f"[info] Matched export cue {ref_id} → recording project "
        f"{rec.project_name} (start={rec.start_sound_path}, end={rec.end_sound_path})"
    )
    return {
        "project_name": rec.project_name,
        "recording": rec,
    }


def match_ableton_export_to_recording(
    audio_path: Path,
    store: ProjectFiles,
):
    cue_info = detect_audio_start_cue(audio_path)
    if not cue_info or not cue_info.get("ref_id"):
        print(f"[warn] No cue found in {audio_path}")
        return None, cue_info

    match = find_ableton_recording_for_export(store, cue_info["ref_id"])
    if not match:
        print(f"[warn] Could not match export {audio_path.name} to any recording.")
        return None, cue_info

    rec = match["recording"]
    project_name = match["project_name"]
    print(
        f"🎛️ Export {audio_path.name} linked to project "
        f"{project_name} (start={rec.start_sound_path}, end={rec.end_sound_path})"
    )
    return match, cue_info


def main():
    if len(sys.argv) < 3:
        print("Usage: python export_matcher.py <path-to-ableton-export> <project_root>")
        sys.exit(1)

    audio_path = Path(sys.argv[1])
    project_root = Path(sys.argv[2])

    if not audio_path.exists():
        print(f"File not found: {audio_path}")
        sys.exit(1)

    store = ProjectFiles(project_root)
    match, cue_info = match_ableton_export_to_recording(audio_path, store)
    print("match:", match)
    print("cue  :", cue_info)


if __name__ == "__main__":
    main()
