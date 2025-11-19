#!/usr/bin/env python3
"""
Ableton Export Matcher (full cue search)
----------------------------------------
Detects cue tones in an Ableton render (MP3/WAV),
matches them to a document in `vincent_core.ableton.recordings`,
and adds a new trait: "ableton_export_match".

Now automatically loads *all* start_*.wav and stop_*.wav cues
from the cue_refs directory tree.
"""

import os
import sys
from datetime import datetime
from pathlib import Path
from pymongo import MongoClient
import numpy as np

# --- hybrid import-safe header ---
if __package__ is None or __package__ == "":
    this_file = Path(__file__).resolve()
    sys.path.append(str(this_file.parent.parent))
    from music_video_generation.postprocessing.audio_utils import read_wav_mono_any as read_wav_mono
    from music_video_generation.postprocessing.config import REF_DIR, FS, MIN_GAP_S
    from music_video_generation.postprocessing.cue_detection import find_all_matches
else:
    from .postprocessing.audio_utils import read_wav_mono_any as read_wav_mono
    from .postprocessing.config import REF_DIR, FS, MIN_GAP_S
    from .postprocessing.cue_detection import find_all_matches

THRESHOLD_DEFAULT = 0.45
THRESHOLD_MP3 = 0.3


# =============================================================
# === Build a complete cue library (recursive search) ===
# =============================================================

def gather_all_cues(refs_dir: Path):
    """Recursively loads all start_*.wav and stop_*.wav cues."""
    start_cues, end_cues = [], []

    for wav in refs_dir.rglob("*.wav"):
        name = wav.name.lower()
        try:
            from music_video_generation.postprocessing.audio_utils import read_wav_mono, fade
            data, fs = read_wav_mono(wav)
            # quick fade to reduce edge artifacts
            n = int(fs * 0.005)
            data[:n] *= np.linspace(0, 1, n)
            data[-n:] *= np.linspace(1, 0, n)
        except Exception as e:
            print(f"[warn] Failed to read {wav.name}: {e}")
            continue

        if "start" in name or "begin" in name or "cue" in name:
            start_cues.append({"id": wav.name, "samples": data})
        elif "stop" in name or "end" in name:
            end_cues.append({"id": wav.name, "samples": data})

    print(f"[info] Loaded {len(start_cues)} start cues, {len(end_cues)} end cues from {refs_dir}")
    return {"start": start_cues, "end": end_cues}


# =============================================================
# === 1️⃣ Cue detection in Ableton exports ===
# =============================================================

def detect_audio_start_cue(audio_path: Path) -> dict | None:
    """
    Detects the unique Ableton start cue in an audio export (MP3/WAV).

    Strategy:
    1️⃣ Optionally detect the common start.wav as a coarse locator.
    2️⃣ Narrow search region ±2s and re-scan with all unique cues.
    3️⃣ Prefer cues whose filename starts with 'start_' over 'start.wav'.
    """

    refs = gather_all_cues(REF_DIR)
    all_starts = refs.get("start", [])
    if not all_starts:
        raise RuntimeError(f"No start cue references found in {REF_DIR}")

    # --- split generic vs unique ---
    generic_start = [r for r in all_starts if r["id"].lower() == "start.wav"]
    unique_starts = [r for r in all_starts if r["id"].lower() != "start.wav"]

    print(f"[info] Using {len(unique_starts)} unique start cues "
          f"and {len(generic_start)} generic start.wav")

    try:
        x, fs = read_wav_mono(audio_path)
    except Exception as e:
        print(f"[warn] Could not read audio {audio_path}: {e}")
        return None

    threshold = THRESHOLD_MP3 if audio_path.suffix.lower() == ".mp3" else THRESHOLD_DEFAULT

    # --- Step 1: try to locate generic start.wav first ---
    coarse_time = None
    if generic_start:
        ref = generic_start[0]
        hits = find_all_matches(ref["samples"], x, threshold * 0.8, MIN_GAP_S)
        if hits:
            idx, score = max(hits, key=lambda h: h[1])
            coarse_time = idx / FS
            print(f"[debug] coarse start.wav match at {coarse_time:.3f}s (score={score:.2f})")

    # --- Step 2: define focused search window ---
    if coarse_time is not None:
        start_i = max(0, int((coarse_time - 1.0) * FS))
        end_i = min(len(x), int((coarse_time + 3.0) * FS))
        segment = x[start_i:end_i]
        segment_offset = start_i / FS
    else:
        segment = x
        segment_offset = 0.0

    # --- Step 3: search all unique cues in that window ---
    best_hit, best_score, best_ref = None, 0.0, None
    for ref in unique_starts:
        hits = find_all_matches(ref["samples"], segment, threshold, MIN_GAP_S)
        for idx, score in hits:
            if score > best_score:
                best_hit = (idx / FS) + segment_offset
                best_score = score
                best_ref = ref["id"]

    # --- Step 4: fallback if nothing unique found ---
    if best_hit is None and coarse_time is not None:
        best_hit, best_ref, best_score = coarse_time, "start.wav", 0.0

    # --- Step 5: result ---
    if best_hit is not None:
        print(
            f"[info] Detected start cue in {audio_path.name}: "
            f"{best_ref} at {best_hit:.3f}s (score={best_score:.2f})"
        )
        return {"time_s": best_hit, "ref_id": best_ref, "score": best_score}

    print(f"[warn] No cue detected in {audio_path.name}")
    return None

# =============================================================
# === 2️⃣ Find the matching Ableton recording ===
# =============================================================

def find_ableton_recording_for_export(client: MongoClient, ref_id: str):
    db = client["vincent_core"]
    coll = db["ableton.recordings"]
    query = {
        "$or": [
            {"fields.ableton_recording.start_sound_path": {"$regex": ref_id}},
            {"fields.ableton_recording.end_sound_path": {"$regex": ref_id}},
        ]
    }
    doc = coll.find_one(query)
    if not doc:
        print(f"[warn] No Ableton recording found for cue {ref_id}")
        return None
    print(f"[info] Matched export cue {ref_id} → recording: {doc.get('title')}")
    return doc


# =============================================================
# === 3️⃣ Attach new trait to the recording ===
# =============================================================

def attach_export_trait(client: MongoClient, rec_doc: dict, audio_path: Path, cue_info: dict):
    db = client["vincent_core"]
    coll = db["ableton.recordings"]

    rec_id = rec_doc["_id"]
    trait_data = {
        "file_path": str(audio_path),
        "cue_ref_id": cue_info["ref_id"],
        "cue_time_s": cue_info["time_s"],
        "cue_score": cue_info["score"],
        "matched_at": datetime.utcnow().isoformat(),
    }

    update_doc = {
        "$addToSet": {"traits": "ableton_export_match"},
        "$set": {f"fields.ableton_export_match": trait_data},
    }

    result = coll.update_one({"_id": rec_id}, update_doc)
    if result.modified_count:
        print(f"✅ Updated recording {rec_doc.get('title')} with ableton_export_match.")
    else:
        print(f"[info] Recording {rec_doc.get('title')} already had export trait.")


# =============================================================
# === 4️⃣ High-level matcher ===
# =============================================================

def match_ableton_export_to_recording(audio_path: Path, client: MongoClient):
    cue_info = detect_audio_start_cue(audio_path)
    if not cue_info or not cue_info.get("ref_id"):
        print(f"[warn] No cue found in {audio_path}")
        return None, None

    rec_doc = find_ableton_recording_for_export(client, cue_info["ref_id"])
    if not rec_doc:
        print(f"[warn] Could not match export {audio_path.name} to any recording.")
        return None, cue_info

    attach_export_trait(client, rec_doc, audio_path, cue_info)

    print(
        f"🎛️ Export {audio_path.name} linked to Ableton project "
        f"{rec_doc['fields']['ableton_recording']['project_name']} "
        f"({rec_doc['title']})"
    )
    return rec_doc, cue_info


# =============================================================
# === 5️⃣ CLI Entry ===
# =============================================================

def main():
    if len(sys.argv) < 2:
        print("Usage: python export_matcher.py <path-to-ableton-export>")
        sys.exit(1)

    audio_path = Path(sys.argv[1])
    if not audio_path.exists():
        print(f"File not found: {audio_path}")
        sys.exit(1)

    client = MongoClient("mongodb://localhost:27025")
    match_ableton_export_to_recording(audio_path, client)


if __name__ == "__main__":
    main()
