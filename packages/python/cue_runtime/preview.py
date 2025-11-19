from __future__ import annotations

import wave
from pathlib import Path
from types import SimpleNamespace
from typing import Mapping, Sequence, Tuple

import numpy as np
try:
    from loguru import logger
except ImportError:  # pragma: no cover - fallback when loguru not installed
        import logging

        logger = logging.getLogger(__name__)

try:
    from music_video_generation.ableton.ableton_recording import AbletonRecording
    from music_video_generation.ableton.recording_manager import (
        START_SEED_GAIN,
        START_SEED_LENGTH,
        STOP_SEED_GAIN,
        STOP_SEED_LENGTH,
    )
except ImportError:  # pragma: no cover - optional dependency
    AbletonRecording = None  # type: ignore
    START_SEED_GAIN = 1.0
    START_SEED_LENGTH = 0.5
    STOP_SEED_GAIN = 1.0
    STOP_SEED_LENGTH = 0.5

try:
    from cue_player import CuePlayer, mk_barker_bpsk, to_stereo, unique_cue
except ImportError:
    try:
        from packages.python.cue_player import CuePlayer, mk_barker_bpsk, to_stereo, unique_cue
    except Exception:  # pragma: no cover
        CuePlayer = None  # type: ignore
        mk_barker_bpsk = None  # type: ignore
        to_stereo = None  # type: ignore
        unique_cue = None  # type: ignore

try:
    from cue_library import CueLibrary
    from cue_library.constants import DEFAULT_SAMPLE_RATE
except ImportError:
    try:
        from packages.python.cue_library import CueLibrary
        from packages.python.cue_library.constants import DEFAULT_SAMPLE_RATE
    except Exception:  # pragma: no cover
        CueLibrary = None  # type: ignore
        DEFAULT_SAMPLE_RATE = 48_000  # type: ignore


def _beats_per_bar(ts_num: int, ts_den: int) -> float:
    return float(ts_num) * (4.0 / float(ts_den if ts_den else 4))


class RecordingCuePreviewer:
    """Recreate the Ableton cue sequence for previously captured recordings."""

    def __init__(self, default_cue_dir: Path | str | None = None) -> None:
        if CueLibrary is None:
            raise RuntimeError("cue_library is required for RecordingCuePreviewer.")
        self._cue_library = CueLibrary(sample_rate=DEFAULT_SAMPLE_RATE, peak_db=0.0)
        if default_cue_dir:
            self._default_cue_dir = Path(default_cue_dir).expanduser().resolve()
        else:
            root = Path(__file__).resolve().parents[4]
            self._default_cue_dir = (
                root
                / "apps"
                / "python"
                / "ableton_video_sync_server"
                / "music_video_generation"
                / "ableton"
                / "cue_refs"
            )

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

        entry = self._normalize_recording(recording)
        cue_dir = self._resolve_cue_dir(entry, project_path)
        start_f32, end_f32 = self._prepare_templates(cue_dir)

        cp = CuePlayer.instance()
        bpb = _beats_per_bar(int(entry.ts_num), int(entry.ts_den))
        start_beats = float(entry.start_recording_bar or 0.0) * bpb
        end_beats = float(entry.end_recording_bar or start_beats) * bpb

        recorded_start_sequence = self._load_recorded_sequence(entry, kind="start")
        recorded_stop_sequence = self._load_recorded_sequence(entry, kind="end")

        recorded_start_seed = None if recorded_start_sequence else self._load_recorded_seed(entry, kind="start")
        recorded_stop_seed = None if recorded_stop_sequence else self._load_recorded_seed(entry, kind="end")

        if verb == "start":
            self._play_start_sequence(
                cp,
                start_f32,
                entry.time_start_recording,
                start_beats,
                entry.bpm_at_start,
                recorded_sequence=recorded_start_sequence,
                recorded_seed=recorded_start_seed,
            )
        else:
            self._play_stop_sequence(
                cp,
                end_f32,
                entry.time_end_recording,
                end_beats,
                entry.bpm_at_start,
                recorded_sequence=recorded_stop_sequence,
                recorded_seed=recorded_stop_seed,
            )

    def _prepare_templates(self, cue_dir: Path) -> Tuple[np.ndarray, np.ndarray]:
        self._cue_library.ensure_primary_references(target_dir=cue_dir)
        start = self._cue_library.to_stereo(self._cue_library.start_cue())
        end = self._cue_library.to_stereo(self._cue_library.end_cue())
        return start, end

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

    @staticmethod
    def _duration_from_audio(stereo: np.ndarray, rate: int | float) -> float:
        if stereo.size == 0 or not rate:
            return 0.0
        return float(len(stereo)) / float(rate)

    def _play_start_sequence(
        self,
        cp,
        template: np.ndarray,
        timestamp: float,
        beats: float,
        bpm: float,
        *,
        recorded_sequence: Tuple[np.ndarray, int, str] | None,
        recorded_seed: Tuple[np.ndarray, int, str] | None,
    ) -> None:
        if recorded_sequence is not None:
            stereo, rate, source = recorded_sequence
            duration = self._duration_from_audio(stereo, rate)
            logger.info("RecordingCuePreviewer: playing recorded START cue from %s (%.3fs)", source, duration)
            cp.play(stereo, samplerate=rate)
            return

        unique_start = self._unique_variant(template, self._timestamp_seed(timestamp))
        unique_dur = self._duration_from_audio(unique_start, cp.fs_out)
        cp.play(unique_start)

        barker = to_stereo(mk_barker_bpsk(chip_ms=18.0, carrier_hz=3200.0, fs=cp.fs_out)) * 1.2
        barker = np.clip(barker, -1.0, 1.0)
        barker_dur = self._duration_from_audio(barker, cp.fs_out)
        cp.play(barker, samplerate=cp.fs_out)

        if recorded_seed is not None:
            stereo, rate, source = recorded_seed
            duration = self._duration_from_audio(stereo, rate)
            logger.info("RecordingCuePreviewer: playing recorded START seed from %s (%.3fs)", source, duration)
            cp.play(stereo, samplerate=rate)
        else:
            seed_val = self._seed_from_ableton_time(beats, bpm)
            seed_stereo = to_stereo(unique_cue(seed_val, length=START_SEED_LENGTH)) * START_SEED_GAIN
            seed_stereo = np.clip(seed_stereo, -1.0, 1.0)
            seed_dur = self._duration_from_audio(seed_stereo, cp.fs_out)
            logger.info(
                "RecordingCuePreviewer: playing synthetic START cue (unique=%.3fs, barker=%.3fs, seed=%.3fs, total=%.3fs)",
                unique_dur,
                barker_dur,
                seed_dur,
                unique_dur + barker_dur + seed_dur,
            )
            cp.play(seed_stereo)

    def _play_stop_sequence(
        self,
        cp,
        template: np.ndarray,
        timestamp: float,
        beats: float,
        bpm: float,
        *,
        recorded_sequence: Tuple[np.ndarray, int, str] | None,
        recorded_seed: Tuple[np.ndarray, int, str] | None,
    ) -> None:
        if recorded_sequence is not None:
            stereo, rate, source = recorded_sequence
            duration = self._duration_from_audio(stereo, rate)
            logger.info("RecordingCuePreviewer: playing recorded STOP cue from %s (%.3fs)", source, duration)
            cp.play(stereo, samplerate=rate)
            return

        unique_stop = self._unique_variant(template, self._timestamp_seed(timestamp))
        unique_dur = self._duration_from_audio(unique_stop, cp.fs_out)
        cp.play(unique_stop)

        barker = to_stereo(mk_barker_bpsk(chip_ms=18.0, carrier_hz=2400.0, fs=cp.fs_out)) * 1.2
        barker = np.clip(barker, -1.0, 1.0)
        barker_dur = self._duration_from_audio(barker, cp.fs_out)
        cp.play(barker, samplerate=cp.fs_out)

        if recorded_seed is not None:
            stereo, rate, source = recorded_seed
            duration = self._duration_from_audio(stereo, rate)
            logger.info("RecordingCuePreviewer: playing recorded STOP seed from %s (%.3fs)", source, duration)
            cp.play(stereo, samplerate=rate)
        else:
            seed_val = self._seed_from_ableton_time(beats, bpm)
            seed_stereo = to_stereo(unique_cue(seed_val, length=STOP_SEED_LENGTH)) * STOP_SEED_GAIN
            seed_stereo = np.clip(seed_stereo, -1.0, 1.0)
            seed_dur = self._duration_from_audio(seed_stereo, cp.fs_out)
            logger.info(
                "RecordingCuePreviewer: playing synthetic STOP cue (unique=%.3fs, barker=%.3fs, seed=%.3fs, total=%.3fs)",
                unique_dur,
                barker_dur,
                seed_dur,
                unique_dur + barker_dur + seed_dur,
            )
            cp.play(seed_stereo)

    def _load_recorded_sequence(self, entry: AbletonRecording, kind: str) -> Tuple[np.ndarray, int, str] | None:
        field = "start_combined_path" if kind == "start" else "end_combined_path"
        path = getattr(entry, field, "")
        if not isinstance(path, str) or not path:
            return None
        try:
            stereo, rate = self._load_audio(path)
            return stereo, rate, path
        except Exception as exc:
            logger.warning("RecordingCuePreviewer: failed to load %s cue sequence %s: %s", kind, path, exc)
            return None

    def _load_recorded_seed(self, entry: AbletonRecording, kind: str) -> Tuple[np.ndarray, int, str] | None:
        field = "start_sound_path" if kind == "start" else "end_sound_path"
        path = getattr(entry, field, "")
        if not isinstance(path, str) or not path:
            return None
        try:
            stereo, rate = self._load_audio(path)
            return stereo, rate, path
        except Exception as exc:
            logger.warning("RecordingCuePreviewer: failed to load %s cue seed %s: %s", kind, path, exc)
            return None

    @staticmethod
    def _load_audio(path: str) -> Tuple[np.ndarray, int]:
        with wave.open(path, "rb") as handle:
            frames = handle.readframes(handle.getnframes())
            sample_width = handle.getsampwidth()
            dtype, scale, offset = RecordingCuePreviewer._dtype_for_width(sample_width)
            raw = np.frombuffer(frames, dtype=dtype).astype(np.float32)
            raw = (raw - offset) / scale if offset else raw / scale
            channels = handle.getnchannels()
            if channels == 1:
                stereo = np.repeat(raw.reshape(-1, 1), 2, axis=1)
            else:
                stereo = raw.reshape(-1, channels)
                if channels > 2:
                    stereo = stereo[:, :2]
            return stereo, handle.getframerate()

    @staticmethod
    def _dtype_for_width(width: int) -> Tuple[np.dtype, float, float]:
        if width == 1:
            return np.uint8, 128.0, 128.0
        if width == 2:
            return np.int16, 32768.0, 0.0
        if width == 4:
            return np.int32, 2147483648.0, 0.0
        raise RuntimeError(f"Unsupported sample width: {width}")


    def _normalize_recording(self, recording: AbletonRecording | Mapping[str, object]):
        if AbletonRecording is not None and isinstance(recording, AbletonRecording):
            return recording
        payload = dict(recording) if isinstance(recording, Mapping) else dict(recording.__dict__)
        if AbletonRecording is not None:
            return AbletonRecording(**payload)
        return SimpleNamespace(**payload)


__all__ = ["RecordingCuePreviewer"]
