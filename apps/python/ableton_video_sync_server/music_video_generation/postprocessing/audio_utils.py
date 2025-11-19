import subprocess, wave, numpy as np
from scipy.signal import fftconvolve
from pathlib import Path
from .config import FS, FADE_MS
import numpy as np
import wave
from pathlib import Path
from scipy.signal import butter, filtfilt

VIDEO_EXT = {".mp4", ".mov", ".mkv", ".avi", ".m4v"}
AUDIO_EXT = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg"}

def run_ffmpeg(cmd):
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr)
    return proc

def has_ffmpeg():
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.run(["ffprobe", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except FileNotFoundError:
        return False

def extract_audio_48k(infile, tmpwav):
    cmd = ["ffmpeg", "-y", "-i", infile, "-ac", "1", "-ar", str(FS), "-vn", "-f", "wav", tmpwav]
    run_ffmpeg(cmd)

def get_media_duration(infile):
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", infile,
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        return float(proc.stdout.strip())
    except Exception:
        return None



def read_wav_mono(path: Path, apply_bandpass: bool = True):
    with wave.open(str(path), "rb") as wf:
        fs = wf.getframerate()
        ch = wf.getnchannels()
        sw = wf.getsampwidth()
        n = wf.getnframes()
        raw = wf.readframes(n)

    # --- decode PCM ---
    if sw == 1:
        x = (np.frombuffer(raw, np.uint8).astype(np.float32) - 128.0) / 128.0
    elif sw == 2:
        x = np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0
    else:
        x = np.frombuffer(raw, np.int32).astype(np.float32) / (2**31)

    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)

    # --- optional band-pass filter (helps detect 2–3 kHz cues) ---
    if apply_bandpass:
        low_hz, high_hz = 800, 3500       # works for both 2.4 kHz and 3.2 kHz cues
        b, a = butter(3, [low_hz / (fs / 2), high_hz / (fs / 2)], btype="band")
        x = filtfilt(b, a, x)

    return x, fs


def fade(x, ms=FADE_MS, fs=FS):
    n = max(1, int(ms * fs / 1000))
    ramp = np.linspace(0, 1, n, dtype=np.float32)
    x[:n] *= ramp
    x[-n:] *= ramp[::-1]
    return x

def norm(x): return (x - np.mean(x)) / (np.std(x) + 1e-8)

def xcorr_valid(ref, rec):
    r = fftconvolve(norm(rec), norm(ref[::-1]), mode="valid")
    r /= max(1, len(ref))
    return r



import subprocess
import tempfile
from pathlib import Path
import numpy as np
import wave

FS = 48000

def ensure_wav_48k(infile: Path) -> Path:
    """If file is not WAV, decode it to temporary mono 48 kHz WAV."""
    if infile.suffix.lower() == ".wav":
        return infile

    tmp = Path(tempfile.gettempdir()) / f"decoded_{infile.stem}.wav"
    cmd = [
        "ffmpeg", "-y",
        "-i", str(infile),
        "-ac", "1",  # mono
        "-ar", str(FS),
        "-vn",
        str(tmp)
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return tmp


def read_wav_mono_any(infile: Path):
    """Reads any audio (WAV/MP3/M4A) as mono float32 @ 48 kHz."""
    wav_path = ensure_wav_48k(infile)

    with wave.open(str(wav_path), "rb") as wf:
        fs = wf.getframerate()
        ch = wf.getnchannels()
        sw = wf.getsampwidth()
        n = wf.getnframes()
        raw = wf.readframes(n)

    if sw == 1:
        x = (np.frombuffer(raw, np.uint8).astype(np.float32) - 128.0) / 128.0
    elif sw == 2:
        x = np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0
    else:
        x = np.frombuffer(raw, np.int32).astype(np.float32) / (2**31)

    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    return x, fs
