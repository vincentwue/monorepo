from __future__ import annotations

import wave
from pathlib import Path
from typing import Mapping, Sequence, Tuple

import numpy as np
from loguru import logger

from music_video_generation.ableton.ableton_recording import AbletonRecording
from music_video_generation.ableton.recording_manager import (
    START_SEED_GAIN,
    START_SEED_LENGTH,
    STOP_SEED_GAIN,
    STOP_SEED_LENGTH,
)

try:
    from .player import CuePlayer, mk_barker_bpsk, to_stereo, unique_cue
    from .generation import ensure_refs as legacy_ensure_refs
except Exception:  # pragma: no cover - playback backend not available during some tests
    CuePlayer = None  # type: ignore
    mk_barker_bpsk = None  # type: ignore
    to_stereo = None  # type: ignore
    unique_cue = None  # type: ignore
    legacy_ensure_refs = None  # type: ignore


def _beats_per_bar(ts_num: int, ts_den: int) -> float:
    return float(ts_num) * (4.0 / float(ts_den if ts_den else 4))


class RecordingCuePreviewer:
    """Recreate the Ableton cue sequence for previously captured recordings."""

    def __init__(self, default_cue_dir: Path | str | None = None) -> None:
        if default_cue_dir:
            self._default_cue_dir = Path(default_cue_dir).expanduser().resolve()
        else:
            root = Path(__file__).resolve().parents[4]
            self._default_cue_dir = root / "apps" / "python" / "ableton_video_sync_server" / "music_video_generation" / "ableton" / "cue_refs"

    def play(
        self,
        recording: AbletonRecording | Mapping[str, object],
        action: str,
        *,
        project_path: str | None = None,
    ) -> None:
        verb = (action or "").strip().lower()
        if verb not in {"start", "stop"}:
            raise ValueError("Action must be 'start' or 'stop'.")
        if CuePlayer is None or mk_barker_bpsk is None or to_stereo is None or unique_cue is None:
            raise RuntimeError("Cue playback backend is not available.")
        if legacy_ensure_refs is None:
            raise RuntimeError("Cue assets are unavailable.")

        entry = recording if isinstance(recording, AbletonRecording) else AbletonRecording(**dict(recording))
        cue_dir = self._resolve_cue_dir(entry, project_path)
        _start_path, _end_path, start_f32, end_f32, _start_pcm, _end_pcm = legacy_ensure_refs(ref_dir=str(cue_dir))

        cp = CuePlayer.instance()
        bpb = _beats_per_bar(int(entry.ts_num), int(entry.ts_den))
        start_beats = float(entry.start_recording_bar or 0.0) * bpb
        end_beats = float(entry.end_recording_bar or start_beats) * bpb

        recorded_start = self._load_recorded_seed(entry, kind="start")
        recorded_end = self._load_recorded_seed(entry, kind="end")

        if verb == "start":
            self._play_start_sequence(
                cp,
                start_f32,
                entry.time_start_recording,
                start_beats,
                entry.bpm_at_start,
                recorded_seed=recorded_start,
            )
        else:
            self._play_stop_sequence(
                cp,
                end_f32,
                entry.time_end_recording,
                end_beats,
                entry.bpm_at_start,
                recorded_seed=recorded_end,
            )

    # ------------------------------------------------------------------ helpers
    def _resolve_cue_dir(self, entry: AbletonRecording, project_path: str | None) -> Path:
        candidates: list[str] = []
        if project_path:
            candidates.append(str(Path(project_path).expanduser().resolve() / "ableton" / "cue_refs"))
        for field in ("start_sound_path", "end_sound_path", "start_combined_path", "end_combined_path"):
            value = getattr(entry, field, "")
            if isinstance(value, str) and value:
                candidates.append(value)
        for raw in candidates:
            try:
                candidate = Path(raw).expanduser().resolve()
                if candidate.is_file():
                    candidate = candidate.parent
                candidate.mkdir(parents=True, exist_ok=True)
                return candidate
            except Exception:
                continue
        self._default_cue_dir.mkdir(parents=True, exist_ok=True)
        return self._default_cue_dir

    @staticmethod
    def _timestamp_seed(timestamp: float) -> int:
        try:
            base = int(round(float(timestamp) * 1000.0))
        except Exception:
            base = 0
        if base <= 0:
            base = 1
        return base

    @staticmethod
    def _seed_from_ableton_time(beats: float, bpm: float) -> int:
        b = int(abs(round((beats or 0.0) * 1000.0)))
        t = int(abs(round((bpm or 0.0) * 100.0)))
        seed = (b ^ (t << 1) ^ 0x9E3779B1) & 0x7FFFFFFF
        return seed if seed > 0 else 1

    @staticmethod
    def _unique_variant(stereo: np.ndarray, seed: int) -> np.ndarray:
        rng = np.random.default_rng(seed)
        data = np.array(stereo, dtype=np.float32)
        overlay_len = min(len(data), int(0.35 * 48000))
        if overlay_len > 0:
            overlay = rng.uniform(-0.25, 0.25, size=(overlay_len, data.shape[1])).astype(np.float32)
            data[:overlay_len] = np.clip(data[:overlay_len] + overlay, -1.0, 1.0)
        tone_len = int(0.25 * 48000)
        t = np.linspace(0, 0.25, tone_len, endpoint=False, dtype=np.float32)
        freq = rng.uniform(650.0, 1400.0)
        extra = (np.sin(2 * np.pi * freq * t) * rng.uniform(0.6, 0.9)).astype(np.float32)
        extra = np.column_stack((extra, extra))
        data = np.concatenate([data, extra], axis=0)
        return np.clip(data, -1.0, 1.0)

    def _play_start_sequence(
        self,
        cp,
        template: np.ndarray,
        timestamp: float,
        beats: float,
        bpm: float,
        *,
        recorded_seed: Tuple[np.ndarray, int, str] | None,
    ) -> None:
        unique_start = self._unique_variant(template, self._timestamp_seed(timestamp))
        cp.play(unique_start)

        barker = to_stereo(mk_barker_bpsk(chip_ms=18.0, carrier_hz=3200.0, fs=cp.fs_out)) * 1.2
        barker = np.clip(barker, -1.0, 1.0)
        cp.play(barker, samplerate=cp.fs_out)

        if recorded_seed is not None:
            stereo, rate, source = recorded_seed
            logger.info("RecordingCuePreviewer: playing recorded START seed from %s", source)
            cp.play(stereo, samplerate=rate)
        else:
            seed_val = self._seed_from_ableton_time(beats, bpm)
            seed_stereo = to_stereo(unique_cue(seed_val, length=START_SEED_LENGTH)) * START_SEED_GAIN
            seed_stereo = np.clip(seed_stereo, -1.0, 1.0)
            cp.play(seed_stereo)

    def _play_stop_sequence(
        self,
        cp,
        template: np.ndarray,
        timestamp: float,
        beats: float,
        bpm: float,
        *,
        recorded_seed: Tuple[np.ndarray, int, str] | None,
    ) -> None:
        unique_end = self._unique_variant(template, self._timestamp_seed(timestamp))
        cp.play(unique_end)

        barker = to_stereo(mk_barker_bpsk(chip_ms=18.0, carrier_hz=2400.0, fs=cp.fs_out)) * 1.2
        barker = np.clip(barker, -1.0, 1.0)
        cp.play(barker, samplerate=cp.fs_out)

        if recorded_seed is not None:
            stereo, rate, source = recorded_seed
            logger.info("RecordingCuePreviewer: playing recorded STOP seed from %s", source)
            cp.play(stereo, samplerate=rate)
        else:
            seed_val = self._seed_from_ableton_time(beats, bpm)
            seed_stereo = to_stereo(unique_cue(seed_val, length=STOP_SEED_LENGTH)) * STOP_SEED_GAIN
            seed_stereo = np.clip(seed_stereo, -1.0, 1.0)
            cp.play(seed_stereo)

    def _load_saved_cue_audio(self, path: str | None) -> Tuple[np.ndarray, int, str] | None:
        if not path:
            return None
        file_path = Path(path)
        if not file_path.exists():
            return None
        with wave.open(str(file_path), "rb") as handle:
            frames = handle.readframes(handle.getnframes())
            width = handle.getsampwidth()
            channels = handle.getnchannels()
            rate = handle.getframerate()
        if width == 1:
            dtype = np.uint8
            offset = 128.0
            scale = 128.0
        elif width == 2:
            dtype = np.int16
            offset = 0.0
            scale = 32768.0
        elif width == 4:
            dtype = np.int32
            offset = 0.0
            scale = 2147483648.0
        else:
            raise RuntimeError(f"Unsupported cue sample width: {width}")
        raw = np.frombuffer(frames, dtype=dtype).astype(np.float32)
        if offset:
            raw = (raw - offset) / scale
        else:
            raw = raw / scale
        if channels == 1:
            stereo = np.column_stack((raw, raw))
        else:
            arr = raw.reshape(-1, channels)
            stereo = arr[:, :2]
        return np.asarray(stereo, dtype=np.float32), rate, str(file_path)

    def _load_recorded_seed(self, entry: AbletonRecording, *, kind: str) -> Tuple[np.ndarray, int, str] | None:
        candidates: Sequence[str | None]
        if kind == "start":
            candidates = [
                getattr(entry, "start_combined_path", "") or None,
                getattr(entry, "start_sound_path", "") or None,
            ]
        else:
            candidates = [
                getattr(entry, "end_combined_path", "") or None,
                getattr(entry, "end_sound_path", "") or None,
            ]
        for candidate in candidates:
            try:
                audio = self._load_saved_cue_audio(candidate)
            except Exception:
                continue
            if audio is not None:
                return audio
        return None


__all__ = ["RecordingCuePreviewer"]
