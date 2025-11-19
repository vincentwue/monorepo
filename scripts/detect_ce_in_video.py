import argparse
import math
import os
import subprocess
import sys
import tempfile

import numpy as np
import soundfile as sf
from scipy.signal import fftconvolve, resample_poly


def run_ffmpeg_extract_audio(video_path: str, target_sr: int = 48000) -> str:
    """
    Extract mono audio from video as 16-bit WAV using ffmpeg into a temp file.
    Returns the path to the temp WAV file.
    """
    tmp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp_wav_path = tmp_wav.name
    tmp_wav.close()

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        video_path,
        "-ac", "1",          # mono
        "-ar", str(target_sr),
        "-vn",               # no video
        "-f", "wav",
        tmp_wav_path,
    ]

    print(f"[ffmpeg] Extracting audio from {video_path} -> {tmp_wav_path}")
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        print("ffmpeg failed:", e.stderr.decode("utf-8", errors="ignore"))
        os.unlink(tmp_wav_path)
        raise

    return tmp_wav_path


def load_mono(path: str):
    data, sr = sf.read(path, always_2d=False)
    # If stereo, average to mono
    if data.ndim > 1:
        data = data.mean(axis=1)
    return data.astype(np.float64), sr


def resample_if_needed(x: np.ndarray, sr_in: int, sr_target: int) -> np.ndarray:
    if sr_in == sr_target:
        return x
    g = math.gcd(sr_in, sr_target)
    up = sr_target // g
    down = sr_in // g
    print(f"[resample] {sr_in} -> {sr_target} (up={up}, down={down})")
    return resample_poly(x, up, down)


def normalized_xcorr(signal: np.ndarray, template: np.ndarray) -> np.ndarray:
    """
    Compute normalized cross-correlation of 'signal' with 'template' (valid region only).
    Returns an array of correlation coefficients between -1 and 1.
    """
    # Center both
    template = template - template.mean()
    signal = signal - signal.mean()

    # Energy of template
    template_energy = np.sum(template ** 2)
    if template_energy == 0:
        raise ValueError("Template has zero energy")

    # Raw cross-correlation via FFT (conv with reversed template)
    corr = fftconvolve(signal, template[::-1], mode="valid")

    # Sliding window energy of signal
    signal_sq = signal ** 2
    window = np.ones(len(template))
    energy = fftconvolve(signal_sq, window, mode="valid")

    # Normalize
    denom = np.sqrt(template_energy * energy)
    with np.errstate(divide="ignore", invalid="ignore"):
        ncc = corr / denom
        ncc[~np.isfinite(ncc)] = 0.0

    return ncc


def find_top_matches(ncc: np.ndarray, sr: int, top_k: int = 5, min_sep_sec: float = 0.2):
    """
    Find top K peaks in ncc, separated by at least min_sep_sec.
    Returns list of (time_sec, score).
    """
    min_sep_samples = int(min_sep_sec * sr)
    ncc_copy = ncc.copy()
    results = []

    for _ in range(top_k):
        idx = np.argmax(ncc_copy)
        score = ncc_copy[idx]
        if score <= 0:
            break
        t = idx / sr
        results.append((t, float(score)))

        # Zero out neighborhood to find next distinct peak
        start = max(0, idx - min_sep_samples)
        end = min(len(ncc_copy), idx + min_sep_samples)
        ncc_copy[start:end] = 0.0

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Detect where a WAV cue appears inside a video (MP4/TS) using normalized cross-correlation."
    )
    # parser.add_argument("--video", required=True, help="Path to video file (e.g. .mp4, .ts)")
    # parser.add_argument("--ref", required=True, help="Path to reference WAV file")
    parser.add_argument("--target-sr", type=int, default=48000, help="Target sample rate for processing (default: 48000)")
    parser.add_argument("--top-k", type=int, default=5, help="Number of top matches to print")
    parser.add_argument("--min-sep", type=float, default=0.2, help="Minimum separation between matches in seconds")

    args = parser.parse_args()

    video_path = r"D:\\music_video_generation\\water\\footage\\videos\\vincent_phone\\PXL_20251119_203951243.TS.mp4"
    ref_path = r"D:\\music_video_generation\\water\\ableton\\cue_refs\\stop_20251119_214024_751.wav"

    if not os.path.isfile(video_path):
        print(f"Video not found: {video_path}")
        sys.exit(1)
    if not os.path.isfile(ref_path):
        print(f"Reference WAV not found: {ref_path}")
        sys.exit(1)

    # 1) Extract audio from video
    tmp_wav_path = None
    try:
        tmp_wav_path = run_ffmpeg_extract_audio(video_path, target_sr=args.target_sr)

        # 2) Load audio and reference
        audio, sr_audio = load_mono(tmp_wav_path)
        ref, sr_ref = load_mono(ref_path)

        print(f"[info] Video audio: {len(audio)} samples @ {sr_audio} Hz")
        print(f"[info] Reference:   {len(ref)} samples @ {sr_ref} Hz")

        # 3) Resample reference if needed
        ref = resample_if_needed(ref, sr_ref, sr_audio)

        if len(ref) >= len(audio):
            print("Reference is longer than or equal to the audio track – nothing to match.")
            sys.exit(1)

        # 4) Compute normalized cross-correlation
        print("[xcorr] Computing normalized cross-correlation...")
        ncc = normalized_xcorr(audio, ref)

        # 5) Find top matches
        top_matches = find_top_matches(ncc, sr_audio, top_k=args.top_k, min_sep_sec=args.min_sep)

        if not top_matches:
            print("No positive correlation peaks found.")
        else:
            best_time, best_score = top_matches[0]
            print("\n=== BEST MATCH ===")
            print(f"Time:  {best_time:.3f} s")
            print(f"Score: {best_score:.3f}")
            print("\n=== TOP MATCHES ===")
            for i, (t, s) in enumerate(top_matches, start=1):
                print(f"{i}. {t:8.3f} s  |  score={s:.3f}")

    finally:
        if tmp_wav_path and os.path.exists(tmp_wav_path):
            try:
                os.unlink(tmp_wav_path)
            except OSError:
                pass


if __name__ == "__main__":
    main()
