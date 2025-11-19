#!/usr/bin/env python3
"""
Ableton Postprocessing → MongoDB
--------------------------------
Detects cue timestamps (start/end) in recordings,
inserts structured results into MongoDB, and shows
a global tqdm progress bar with optional inner logging.
"""

import sys
import time
import tempfile
import traceback
from pathlib import Path
from pymongo import MongoClient
from tqdm import tqdm

from .config import MONGO_URI, INPUT_PATH, REF_DIR, THRESHOLD, MIN_GAP_S, FS
from .audio_utils import has_ffmpeg, extract_audio_48k, read_wav_mono, get_media_duration
from .cue_detection import gather_reference_library, compute_matches, build_segments
from .mongo_writer import insert_postprocessing_result

# =============================================================
# === Settings ===
# =============================================================

VIDEO_EXT = {".mp4", ".mov", ".mkv", ".avi", ".m4v"}
AUDIO_EXT = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg"}

VERBOSE = True  # set to False for silent inner logging

# =============================================================
# === Helpers ===
# =============================================================

def iter_media(path):
    """Recursively yield video/audio file paths under the given folder."""
    for q in Path(path).rglob("*"):
        if q.suffix.lower() in VIDEO_EXT.union(AUDIO_EXT):
            yield str(q)

# =============================================================
# === Core Processing ===
# =============================================================

def process_one(infile, refs, verbose=VERBOSE):
    """Extract audio, detect cues, build segments, and return result dict."""
    t0 = time.perf_counter()
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td) / "audio.wav"

        if verbose:
            tqdm.write(f"⏳ Extracting audio from {Path(infile).name} ...")
        extract_audio_48k(infile, tmp)

        if verbose:
            tqdm.write("🎵 Reading waveform ...")
        rec, fs = read_wav_mono(tmp)

        if verbose:
            tqdm.write("🔍 Detecting cue matches ...")
        matches = compute_matches(rec, refs, THRESHOLD, MIN_GAP_S)

        duration = get_media_duration(infile) or len(rec) / FS
        segs = build_segments(matches["start"], matches["end"], duration)
        cue_ids = sorted(
            set([h["ref_id"] for h in matches["start"]] + [h["ref_id"] for h in matches["end"]])
        )

        elapsed = time.perf_counter() - t0
        if verbose:
            tqdm.write(f"✅ {len(segs)} segment(s) detected in {elapsed:.1f}s\n")

        return {
            "file": infile,
            "duration_s": duration,
            "segments": segs,
            "cue_refs_used": cue_ids,
            "notes": [],
        }

# =============================================================
# === Main Entry ===
# =============================================================

def main():
    if not has_ffmpeg():
        print("⚠️ ffmpeg not found in PATH.")
        sys.exit(1)

    print("🎬 Gathering reference cues ...")
    refs = gather_reference_library(REF_DIR)

    print(f"📂 Scanning input folder: {INPUT_PATH}")
    inputs = list(iter_media(INPUT_PATH))
    if not inputs:
        print("❌ No media files found.")
        sys.exit(1)

    client = MongoClient(MONGO_URI)

    print(f"🔍 Found {len(inputs)} media file(s). Starting postprocessing...\n")

    # --- global tqdm bar ---
    for f in tqdm(inputs, desc="Processing files", unit="file", ncols=100, colour="cyan"):
        try:
            tqdm.write(f"🎧 {Path(f).name}")
            res = process_one(f, refs)
            insert_postprocessing_result(client, res)
        except Exception as e:
            tqdm.write(f"⚠️ Error processing {f}: {e}")
            traceback.print_exc()

    print("\n✅ All files processed successfully.")

# =============================================================
# === Entry Point ===
# =============================================================

if __name__ == "__main__":
    main()
