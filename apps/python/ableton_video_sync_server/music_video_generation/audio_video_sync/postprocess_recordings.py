# batch_sync_and_cut.py  detect START/END cues (from SCRIPT1) and cut media
# Scans a folder for videos and audio. For videos, uses the video's own audio as sync source.
# For audio files (e.g., MP3), uses that audio. Exports summarized cue timestamps.

import json
import subprocess, tempfile, os, csv, sys
import traceback

import numpy as np
import wave
from scipy.signal import fftconvolve
from typing import Dict, Iterable, List, Optional, Tuple
from pathlib import Path

# ===================== CONFIG (edit here) =====================

INPUT_PATH = r"D:\music_video_generation\todo_song\footage\videos"
# OUT_DIR = "cuts"  # output folder for segments and summary.csv
from pathlib import Path

# absolute dir where this script lives
SCRIPT_DIR = Path(__file__).resolve().parent

# cue_refs inside that dir
REF_DIR = SCRIPT_DIR / "cue_refs"

THRESHOLD = 0.5  # cross-corr threshold (0..1, lower is more permissive)
MIN_GAP_S = 0.25  # minimum separation between matches (seconds)
REENCODE = True  # True = accurate re-encode; False = stream copy
# =============================================================

# --- Constants must match SCRIPT1 ---
FS = 48000
START_NAME = "start"
END_NAME = "end"
FADE_MS = 8

VIDEO_EXT = {".mp4", ".mov", ".mkv", ".avi", ".m4v"}
AUDIO_EXT = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg"}


# ---------------- ffmpeg helpers ----------------
def run_ffmpeg(cmd):
    proc = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg error:\n{proc.stderr}")
    return proc


def has_ffmpeg():
    try:
        subprocess.run(
            ["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        subprocess.run(
            ["ffprobe", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        return True
    except FileNotFoundError:
        return False


def get_media_duration(infile):
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        infile,
    ]
    proc = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    if proc.returncode != 0:
        return None
    try:
        return float(proc.stdout.strip())
    except Exception:
        return None


def extract_audio_48k(infile, tmpwav):
    # mono, 48k, 16-bit
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        infile,
        "-ac",
        "1",
        "-ar",
        str(FS),
        "-vn",
        "-f",
        "wav",
        tmpwav,
    ]
    run_ffmpeg(cmd)


def cut_media(infile, start_s, end_s, outfile, reencode=False):
    os.makedirs(os.path.dirname(outfile) or ".", exist_ok=True)
    dur = None if end_s is None else max(0.0, end_s - start_s)
    if reencode:
        cmd = ["ffmpeg", "-y", "-ss", f"{start_s:.6f}", "-i", infile]
        if dur is not None:
            cmd += ["-t", f"{dur:.6f}"]
        cmd += [
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "18",
            "-c:a",
            "aac",
            "-movflags",
            "+faststart",
            outfile,
        ]
        print(outfile)
    else:
        cmd = ["ffmpeg", "-y", "-ss", f"{start_s:.6f}", "-i", infile]
        if dur is not None:
            cmd += ["-t", f"{dur:.6f}"]
        cmd += ["-c", "copy", outfile]
    run_ffmpeg(cmd)


# ---------------- WAV helpers ----------------
def read_wav_mono(path):
    with wave.open(path, "rb") as wf:
        fs = wf.getframerate()
        ch = wf.getnchannels()
        sw = wf.getsampwidth()
        n = wf.getnframes()
        raw = wf.readframes(n)

    if sw not in (1, 2, 3, 4):
        raise ValueError(f"Unsupported sample width {sw} in {path}")

    if sw == 1:
        dtype = np.uint8
        x = (np.frombuffer(raw, dtype=dtype).astype(np.float32) - 128.0) / 128.0
    elif sw == 2:
        dtype = np.int16
        x = np.frombuffer(raw, dtype=dtype).astype(np.float32) / 32768.0
    elif sw == 3:
        a = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3)
        b = np.zeros((a.shape[0], 4), dtype=np.uint8)
        b[:, :3] = a
        x = b.view(np.int32).astype(np.float32) / (2**31)
    else:  # sw == 4
        dtype = np.int32
        x = np.frombuffer(raw, dtype=dtype).astype(np.float32) / (2**31)

    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    return x, fs


def load_ref(path):
    x, fs = read_wav_mono(path)
    if fs != FS:
        raise ValueError(f"Reference must be {FS} Hz: {path} got {fs}")
    return x


def fade(x: np.ndarray, ms: float = FADE_MS, fs: int = FS) -> np.ndarray:
    n = max(1, int(ms * fs / 1000))
    ramp = np.linspace(0, 1, n, dtype=np.float32)
    x[:n] *= ramp
    x[-n:] *= ramp[::-1]
    return x


# ---------------- detection helpers ----------------
def norm(x):
    x = x - np.mean(x)
    s = np.std(x) + 1e-8
    return x / s


def xcorr_valid(ref, rec):
    r = fftconvolve(norm(rec), norm(ref[::-1]), mode="valid")
    r /= max(1, len(ref))
    return r


def find_all_matches(ref, rec, threshold, min_sep_s, verbose=False):
    cor = xcorr_valid(ref, rec)

    if verbose:
        print(f"Max correlation in clip: {np.max(cor):.4f}")

    nms = int(max(1, round(min_sep_s * FS)))
    peaks = []
    i = 0
    L = len(cor)

    while i < L:
        if cor[i] >= threshold:
            j_end = min(L, i + nms)
            j = i + int(np.argmax(cor[i:j_end]))
            score = float(cor[j])
            peaks.append((j, score))
            i = j + nms
        else:
            i += 1
    return peaks

def classify_reference_name(name: str) -> Optional[str]:
    lower = name.lower()
    if any(token in lower for token in ("stop", "end", "finish")):
        return "end"
    if any(token in lower for token in ("start", "begin", "cue_start")):
        return "start"
    return None


def mk_barker_bpsk(chip_ms: float, carrier_hz: float, fs: int = FS) -> np.ndarray:
    barker = np.array([+1, +1, +1, +1, +1, -1, -1, +1, +1, -1, +1, -1, +1], dtype=np.float32)
    chip_n = max(1, int(round(fs * (chip_ms / 1000.0))))
    t_chip = np.linspace(0.0, chip_ms / 1000.0, chip_n, endpoint=False, dtype=np.float32)
    carrier = np.sin(2 * np.pi * carrier_hz * t_chip).astype(np.float32)
    parts = [(bit * carrier) for bit in barker]
    x = np.concatenate(parts).astype(np.float32)
    # Soft fade avoids spurious peaks at edges
    return fade(x, ms=FADE_MS * 2, fs=fs)


def gather_reference_library(refs_dir: Path) -> Dict[str, List[Dict[str, object]]]:
    library: Dict[str, List[Dict[str, object]]] = {"start": [], "end": []}
    if refs_dir.exists():
        for wav_path in sorted(refs_dir.glob("*.wav")):
            kind = classify_reference_name(wav_path.name)
            if not kind:
                continue
            try:
                data = load_ref(wav_path)
            except Exception as exc:
                print(f"[WARN] Failed to load reference {wav_path}: {exc}", file=sys.stderr)
                continue
            library[kind].append(
                {
                    "id": wav_path.name,
                    "label": kind,
                    "source": "file",
                    "path": str(wav_path),
                    "samples": data,
                    "duration_s": len(data) / FS,
                }
            )
    # Add built-in Barker markers (helps if unique cues are missing)
    for kind, freq in (("start", 3200.0), ("end", 2400.0)):
        data = mk_barker_bpsk(chip_ms=18.0, carrier_hz=freq, fs=FS)
        library[kind].append(
            {
                "id": f"barker_{kind}_{int(freq)}hz",
                "label": kind,
                "source": "generated:barker",
                "path": None,
                "samples": data,
                "duration_s": len(data) / FS,
            }
        )
    return library


def compute_matches(rec: np.ndarray, refs: Dict[str, List[Dict[str, object]]], threshold: float, min_gap_s: float) -> Dict[str, List[Dict[str, object]]]:
    matches: Dict[str, List[Dict[str, object]]] = {"start": [], "end": []}
    for kind, ref_list in refs.items():
        for ref in ref_list:
            samples = ref["samples"]
            min_sep = max(min_gap_s, len(samples) / FS)
            hits = find_all_matches(samples, rec, threshold, min_sep, verbose=False)
            for idx, score in hits:
                matches[kind].append(
                    {
                        "label": kind.upper(),
                        "sample_index": int(idx),
                        "time_s": float(idx / FS),
                        "score": float(score),
                        "ref_id": ref["id"],
                        "ref_source": ref["source"],
                        "ref_path": ref.get("path"),
                    }
                )
    for kind in matches:
        matches[kind].sort(key=lambda item: item["sample_index"])
    return matches


def cluster_hits(hits: List[Dict[str, object]], cluster_window_s: float, event_type: str) -> List[Dict[str, object]]:
    if not hits:
        return []
    clusters: List[Dict[str, object]] = []

    for hit in hits:
        if not clusters:
            clusters.append(
                {
                    "event_type": event_type.upper(),
                    "hits": [hit],
                    "time_s": hit["time_s"],
                    "last_time_s": hit["time_s"],
                    "max_score": hit["score"],
                }
            )
            continue

        last = clusters[-1]
        if float(hit["time_s"]) - float(last["last_time_s"]) <= cluster_window_s:
            last["hits"].append(hit)
            last["last_time_s"] = hit["time_s"]
            last["max_score"] = max(float(last["max_score"]), float(hit["score"]))
        else:
            clusters.append(
                {
                    "event_type": event_type.upper(),
                    "hits": [hit],
                    "time_s": hit["time_s"],
                    "last_time_s": hit["time_s"],
                    "max_score": hit["score"],
                }
            )

    for idx, cluster in enumerate(clusters, start=1):
        cluster["cluster_id"] = idx
        cluster["time_s"] = float(cluster["hits"][0]["time_s"])
        cluster["last_time_s"] = float(cluster["last_time_s"])
        cluster["centroid_time_s"] = float(
            sum(float(hit["time_s"]) for hit in cluster["hits"]) / len(cluster["hits"])
        )
        cluster["max_score"] = float(cluster["max_score"])
        cluster["ref_ids"] = sorted({hit["ref_id"] for hit in cluster["hits"] if hit.get("ref_id")})
    return clusters


def _make_segment_payload(
    start_cluster: Optional[Dict[str, object]],
    end_cluster: Optional[Dict[str, object]],
    duration: Optional[float],
    fallback_duration: Optional[float],
) -> Dict[str, object]:
    start_time = float(start_cluster["time_s"]) if start_cluster else None
    end_time = float(end_cluster["time_s"]) if end_cluster else None

    assumed_end = None
    if end_time is None:
        if duration is not None:
            assumed_end = float(duration)
        elif fallback_duration is not None:
            assumed_end = float(fallback_duration)

    duration_s = None
    if start_time is not None and (end_time is not None or assumed_end is not None):
        stop_time = end_time if end_time is not None else assumed_end
        if stop_time is not None:
            duration_s = max(0.0, float(stop_time) - float(start_time))

    payload: Dict[str, object] = {
        "start_time_s": start_time,
        "end_time_s": end_time,
        "assumed_end_time_s": assumed_end,
        "duration_s": duration_s,
        "start_event": start_cluster,
        "end_event": end_cluster,
        "edge_case": None,
    }
    if start_time is None:
        payload["edge_case"] = "missing_start"
    elif end_time is None:
        payload["edge_case"] = "missing_end"
    return payload


def build_segments(
    start_clusters: List[Dict[str, object]],
    end_clusters: List[Dict[str, object]],
    duration: Optional[float],
    fallback_duration: Optional[float],
) -> Tuple[List[Dict[str, object]], List[Dict[str, object]]]:
    segments: List[Dict[str, object]] = []
    unmatched_end_clusters: List[Dict[str, object]] = []
    start_idx = 0
    end_idx = 0

    while start_idx < len(start_clusters) and end_idx < len(end_clusters):
        start_cluster = start_clusters[start_idx]
        end_cluster = end_clusters[end_idx]
        if float(end_cluster["time_s"]) <= float(start_cluster["time_s"]):
            orphan = dict(end_cluster)
            orphan["edge_case"] = "end_without_start"
            unmatched_end_clusters.append(orphan)
            end_idx += 1
            continue

        segments.append(
            _make_segment_payload(start_cluster, end_cluster, duration, fallback_duration)
        )
        start_idx += 1
        end_idx += 1

    for idx in range(start_idx, len(start_clusters)):
        start_cluster = start_clusters[idx]
        segments.append(
            _make_segment_payload(start_cluster, None, duration, fallback_duration)
        )

    for idx in range(end_idx, len(end_clusters)):
        orphan = dict(end_clusters[idx])
        orphan["edge_case"] = "end_without_start"
        unmatched_end_clusters.append(orphan)

    for seg_idx, segment in enumerate(segments, start=1):
        segment["index"] = seg_idx
        segment["loop_footage"] = seg_idx > 1
        if segment.get("edge_case") is None:
            segment["edge_case"] = None

    return segments, unmatched_end_clusters


# ---------------- discovery helpers ----------------
def is_video(path: Path) -> bool:
    return path.suffix.lower() in VIDEO_EXT


def is_audio(path: Path) -> bool:
    return path.suffix.lower() in AUDIO_EXT


def iter_media(path):
    p = Path(path)
    if p.is_file():
        if is_video(p) or is_audio(p) and not "seg" in p.name:
            yield str(p)
    else:
        for q in p.rglob("*"):
            if q.is_file() and (is_video(q) or is_audio(q)) and not "seg" in p.name:
                yield str(q)


# ---------------- processing ----------------
def process_one(infile, refs_dir, threshold, min_gap_s):
    p = Path(infile)
    if not (is_video(p) or is_audio(p)):
        return {"file": infile, "skipped": "unsupported extension"}
    refs_dir_path = Path(refs_dir)
    ref_library = gather_reference_library(refs_dir_path)
    if not ref_library["start"]:
        return {"file": infile, "error": f"no START references found in {refs_dir_path}"}
    if not ref_library["end"]:
        return {"file": infile, "error": f"no END references found in {refs_dir_path}"}

    with tempfile.TemporaryDirectory() as td:
        tmpwav = os.path.join(td, "audio.wav")
        try:
            # Always extract audio from *this* file (video or audio)
            extract_audio_48k(infile, tmpwav)
        except Exception as e:
            return {"file": infile, "error": f"audio extract failed: {e}"}

        rec, fs = read_wav_mono(tmpwav)
        if fs != FS:
            return {"file": infile, "error": f"temp wav not {FS} Hz (got {fs})"}

        matches = compute_matches(rec, ref_library, threshold, min_gap_s)
        start_clusters = cluster_hits(matches["start"], cluster_window_s=min_gap_s, event_type="START")
        end_clusters = cluster_hits(matches["end"], cluster_window_s=min_gap_s, event_type="END")

        waveform_duration = len(rec) / FS
        duration = get_media_duration(infile)

        segments, orphan_end_clusters = build_segments(
            start_clusters, end_clusters, duration, waveform_duration
        )

        notes: List[str] = []
        if not start_clusters:
            notes.append("no_start_cues_detected")
        if not end_clusters:
            notes.append("no_end_cues_detected")
        open_segments = [seg for seg in segments if seg.get("edge_case") == "missing_end"]
        if open_segments:
            notes.append("start_without_end")
        if orphan_end_clusters:
            notes.append("end_without_start")

        return {
            "file": infile,
            "duration_s": float(duration) if duration is not None else None,
            "waveform_duration_s": float(waveform_duration),
            "start_events": start_clusters,
            "end_events": end_clusters,
            "segments": segments,
            "orphan_end_events": orphan_end_clusters,
            "notes": notes,
        }

def write_summary(rows, summary_root_dir):
    """
    Persist cue detection summaries as JSON for downstream tooling / UI.
    """
    os.makedirs(summary_root_dir, exist_ok=True)
    json_path = os.path.join(summary_root_dir, "cue_timestamp_summary.json")
    serializable: List[Dict[str, object]] = []

    for entry in rows:
        if entry is None:
            continue
        payload = {
            "file": entry.get("file"),
            "duration_s": entry.get("duration_s"),
            "waveform_duration_s": entry.get("waveform_duration_s"),
            "segments": entry.get("segments", []),
            "start_events": entry.get("start_events", []),
            "end_events": entry.get("end_events", []),
            "orphan_end_events": entry.get("orphan_end_events", []),
            "notes": entry.get("notes", []),
            "error": entry.get("error"),
            "skipped": entry.get("skipped"),
        }
        serializable.append(payload)

    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(serializable, fh, indent=2)

    # Optional flat CSV for quick inspection
    csv_path = os.path.join(summary_root_dir, "cue_timestamp_segments.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "file",
                "segment_index",
                "start_time_s",
                "end_time_s",
                "assumed_end_time_s",
                "duration_s",
                "loop_footage",
                "edge_case",
                "notes",
            ]
        )
        for entry in serializable:
            file = entry.get("file")
            notes = ";".join(entry.get("notes", []) or [])
            for seg in entry.get("segments") or []:
                writer.writerow(
                    [
                        file,
                        seg.get("index"),
                        seg.get("start_time_s"),
                        seg.get("end_time_s"),
                        seg.get("assumed_end_time_s"),
                        seg.get("duration_s"),
                        seg.get("loop_footage"),
                        seg.get("edge_case"),
                        notes,
                    ]
                )

    return {"json": json_path, "csv": csv_path}
# --- replace postprocess_recordings() so it no longer uses OUT_DIR and writes summary to INPUT_PATH ---
def postprocess_recordings(input_path: str = INPUT_PATH):
    if not has_ffmpeg():
        print("ffmpeg/ffprobe not found in PATH.", file=sys.stderr)
        sys.exit(2)

    inputs = list(iter_media(input_path))
    if not inputs:
        print("No media files found.", file=sys.stderr)
        sys.exit(1)

    results = []
    for f in inputs:
        print(f"Processing: {f}")
        res = process_one(
            infile=f,
            refs_dir=REF_DIR,
            threshold=THRESHOLD,
            min_gap_s=MIN_GAP_S,
        )
        results.append(res)
        if res is None:
            print("WARNING: empty result for file", f)
            continue
        if "error" in res:
            print(f"  -> ERROR: {res['error']}")
        elif res.get("skipped"):
            print(f"  -> SKIPPED: {res['skipped']}")
        else:
            segs = res.get("segments") or []
            print(f"  -> {len(segs)} segment(s) detected.")
            if res.get("notes"):
                for note in res["notes"]:
                    print(f"     note: {note}")
            orphan = res.get("orphan_end_events") or []
            if orphan:
                print(f"     warning: {len(orphan)} END cue(s) without matching START.")

    summary_paths = write_summary(results, summary_root_dir=input_path)
    print(
        "\nCue timestamp summaries written to: "
        f"{summary_paths['json']} (JSON), {summary_paths['csv']} (CSV)"
    )


if __name__ == "__main__":
    postprocess_recordings()
