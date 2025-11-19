from __future__ import annotations
import json, math, threading, time, os, wave, shutil
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple
import numpy as np

from loguru import logger
from pydantic import BaseModel, Field


from music_video_generation.ableton.ableton_recording import AbletonRecording
from music_video_generation.ableton.ableton_recording_session import AbletonRecordingSession
from packages.python.live_rpyc.live_client import LiveClient

# Audio cue plumbing
try:
    from music_video_generation.sound.cue_player import CuePlayer, to_stereo, mk_barker_bpsk, unique_cue
    from music_video_generation.sound.audio_output_selection import AudioOutputSelector
    from music_video_generation.sound.sync_sound_generation.generate_audio_trigger_legacy import (
        ensure_refs as _legacy_ensure_refs,
    )
    from music_video_generation.sound.sync_sound_generation.stop_unique_sound import mk_stop_unique, ensure_stop_ref
    from music_video_generation.sound.cue_output_service import CueOutputService
    from music_video_generation.ableton.recording_state import RecordingStateStore
except Exception:
    CuePlayer = None  # type: ignore
    to_stereo = None  # type: ignore
    AudioOutputSelector = None  # type: ignore
    _legacy_ensure_refs = None  # type: ignore
    mk_stop_unique = None  # type: ignore
    ensure_stop_ref = None  # type: ignore
    CueOutputService = None  # type: ignore
    RecordingStateStore = None  # type: ignore


START_SEED_LENGTH = 0.75
START_SEED_GAIN = 2.2
STOP_SEED_LENGTH = 0.95
STOP_SEED_GAIN = 2.0


def beats_to_seconds(beats: float, bpm: float) -> float:
    return 0.0 if bpm <= 0 else (60.0 / bpm) * beats


def beats_per_bar(ts_num: int, ts_den: int) -> float:
    return float(ts_num) * (4.0 / float(ts_den if ts_den else 4))


class _DBEnvelope(BaseModel):
    version: int = 1
    sessions: List[AbletonRecordingSession] = Field(default_factory=list)



class RecordingManager:
    """
    Singleton that:
       Subscribes to Live record on/off (and count-in) to create AbletonRecording instances.
       Keeps an AbletonRecordingSession per Live Set (by file_path+name).
       Persists all sessions/recordings to JSON next to the Ableton project (or home fallback).
       Exposes:
          - add_on_record_end_listener(callable)
          - get_all_recordings() -> List[AbletonRecording]  (for current session)
          - get_all_sessions() -> List[AbletonRecordingSession]
    """
    _instance: Optional["RecordingManager"] = None
    _lock = threading.Lock()

    # ---- lifecycle ---------------------------------------------------------
    @classmethod
    def instance(cls) -> "RecordingManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self) -> None:
        # state
        self.client = LiveClient.get_instance()
        self.song = self.client.get_song()
        try:
            prev_cb = getattr(self.client, "on_reconnected", None)

            def _on_reconnected_chain() -> None:
                if prev_cb:
                    try:
                        prev_cb()
                    except Exception as exc:  # pragma: no cover - defensive
                        logger.warning(f"Upstream on_reconnected callback failed: {exc}")
                self._handle_live_reconnected()

            self.client.on_reconnected = _on_reconnected_chain  # type: ignore[attr-defined]
        except AttributeError:
            logger.debug("LiveClient does not support on_reconnected callback.")
        self._warned_unsaved_project = False

        # callbacks after a recording is captured
        self._on_record_end_callbacks: List[Callable[[AbletonRecording], None]] = []

        # DB path
        project_folder = self._current_project_folder()
        if project_folder:
            self.db_path = Path(project_folder) / "ableton_recordings_db.json"
        else:
            fallback = Path.home() / "AbletonVideoSync"
            self.db_path = fallback / "ableton_recordings_db.json"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info("RecordingManager using local DB path: %s", self.db_path)

        # envelope (in-memory)
        self._env: _DBEnvelope = self._load_db()

        # per-recording transient markers
        self._await_count_in = False
        self._t0_wall: Optional[float] = None
        self._t1_wall: Optional[float] = None

        self._rec_start_beats: Optional[float] = None
        self._rec_start_bpm: float = float(self.song.tempo)
        self._ts_num: int = int(getattr(self.song, "time_signature_numerator", 4))
        self._ts_den: int = int(getattr(self.song, "time_signature_denominator", 4))

        self._loop_start_b: float = float(getattr(self.song, "loop_start", 0.0))
        self._loop_len_b: float = float(getattr(self.song, "loop_length", 0.0))

        # cue paths for current recording window
        self._start_cue_path: str = ""
        self._stop_cue_path: str = ""
        self._start_combined_path: str = ""
        self._stop_combined_path: str = ""
        # snapshot of armed tracks at record start
        self._armed_track_names: List[str] = []
        self._cue_output_service = CueOutputService() if CueOutputService is not None else None
        self._recording_state_store = RecordingStateStore() if RecordingStateStore is not None else None
        self._capture_this_take = True
        self._cues_this_take = True
        self._default_cue_dir = Path(__file__).resolve().parents[3] / "cue_refs"

        # attach listeners
        self._register_live_listeners()
        # Immediately warn if no project path is set (right after connect)
        try:
            self._maybe_warn_unsaved_project()
        except Exception:
            pass
        # Select a screen/HDMI audio output for cue playback
        configured_cue_device = False
        try:
            if self._cue_output_service is not None and CuePlayer is not None:
                prefs = self._cue_output_service.apply_saved_preferences()
                configured_cue_device = prefs.device_index is not None
                logger.info(
                    "Loaded cue speaker preferences (device=%s, volume=%.2f)",
                    prefs.device_index,
                    prefs.volume,
                )
        except Exception as e:
            logger.warning(f"Failed to apply saved cue preferences: {e}")
        if not configured_cue_device:
            try:
                if CuePlayer is not None and AudioOutputSelector is not None:
                    selector = AudioOutputSelector()
                    device_index = selector.auto_select_output()
                    cp = CuePlayer.instance()
                    cp.device_index = device_index
                    logger.info(
                        f"Set CuePlayer output to device {device_index}: {selector.devices[device_index]['name']}"
                    )
            except Exception as e:
                logger.warning(f"Audio output auto-select failed: {e}")

    # ---- public API --------------------------------------------------------
    def add_on_record_end_listener(self, cb: Callable[[AbletonRecording], None]) -> None:
        """Register a callback to be invoked with the AbletonRecording when recording stops."""
        with self._lock:
            self._on_record_end_callbacks.append(cb)

    def get_all_sessions(self) -> List[AbletonRecordingSession]:
        with self._lock:
            return list(self._env.sessions)

    def get_current_session(self) -> AbletonRecordingSession:
        """Fetch/create the session for the current Live Set."""
        name = str(getattr(self.song, "name", "") or "")
        song_obj = getattr(self, "song", None)
        if song_obj is None:
            logger.warning("RecordingManager: Live song unavailable; requesting reconnect.")
            try:
                LiveClient.get_instance().request_reconnect()
            except Exception as exc:
                logger.error(f"RecordingManager: failed to request reconnect: {exc}")
            return
        try:
            path = str(getattr(song_obj, "file_path", "") or "")
        except Exception as exc:
            logger.warning(f"RecordingManager: unable to read Live project path ({exc}); waiting for reconnect.")
            try:
                LiveClient.get_instance().request_reconnect()
            except Exception as inner_exc:
                logger.error(f"RecordingManager: failed to request reconnect: {inner_exc}")
            return
        key = (name, path)

        with self._lock:
            # try to find an existing session
            for s in self._env.sessions:
                if s.project_name == key[0] and s.file_path == key[1]:
                    return s
            # else create one
            session = AbletonRecordingSession(project_name=key[0], file_path=key[1])
            self._env.sessions.append(session)
            self._save_db()
            return session

    def get_all_recordings(self) -> List[AbletonRecording]:
        """Return all recordings for the *current* session."""
        return list(self.get_current_session().recordings)

    # ---- Live event plumbing -----------------------------------------------
    def _register_live_listeners(self) -> None:
        c = self.client
        if hasattr(c, "on_record_mode"):
            logger.info("RecordingManager: binding on_record_mode listener.")
            c.on_record_mode(lambda s: self._on_record_mode(s))
        else:
            logger.warning("RecordingManager: LiveClient missing on_record_mode listener.")
        if hasattr(c, "on_is_counting_in"):
            logger.info("RecordingManager: binding on_is_counting_in listener.")
            c.on_is_counting_in(lambda s: self._on_count_in(s))
        else:
            logger.warning("RecordingManager: LiveClient missing on_is_counting_in listener.")
        logger.info("RecordingManager: listeners registered (record_mode, is_counting_in).")

    def _handle_live_reconnected(self) -> None:
        """Refresh cached song references and re-register listeners after Live reconnects."""
        logger.info("RecordingManager: LiveClient reported reconnect; refreshing state.")
        try:
            self.song = self.client.get_song()
            self._rec_start_bpm = float(getattr(self.song, "tempo", self._rec_start_bpm))
            self._ts_num = int(getattr(self.song, "time_signature_numerator", self._ts_num))
            self._ts_den = int(getattr(self.song, "time_signature_denominator", self._ts_den))
            self._loop_start_b = float(getattr(self.song, "loop_start", self._loop_start_b))
            self._loop_len_b = float(getattr(self.song, "loop_length", self._loop_len_b))
        except Exception as exc:
            logger.warning(f"RecordingManager: failed to refresh Live song reference after reconnect: {exc}")
            return
        try:
            self._register_live_listeners()
        except Exception as exc:
            logger.warning(f"RecordingManager: failed to rebind listeners after reconnect: {exc}")

    def _on_count_in(self, s) -> None:
        logger.debug("RecordingManager:_on_count_in triggered (counting_in=%s)", getattr(s, "is_counting_in", None))
        if self._await_count_in and not bool(getattr(s, "is_counting_in", False)):
            self._mark_start(s)

    def _on_record_mode(self, s) -> None:
        logger.debug(
            "RecordingManager:_on_record_mode event (record_mode=%s, counting_in=%s)",
            getattr(s, "record_mode", None),
            getattr(s, "is_counting_in", None),
        )

        path = str(getattr(self.song, "file_path", "") or "")
        if not path:
            logger.warning("[WARN] No project path set  cannot sync recordings to MongoDB.")
            self.warn_user_to_save_project()
            return

        if bool(getattr(s, "record_mode", False)):
            # Record ON
            self._await_count_in = bool(getattr(s, "is_counting_in", False))
            if self._await_count_in:
                logger.info(" Record ON  waiting for count-in to finish...")
            else:
                self._mark_start(s)
        else:
            # Record OFF
            if self._t0_wall is None:
                # safety: mark start now if we somehow missed it
                self._mark_start(s)
            self._t1_wall = time.time()
            try:
                self._play_on_stop(s)
            except Exception as exc:
                logger.warning(f"Failed to emit stop cue inline: {exc}")
            logger.info(" Record OFF.")
            rec = self._build_recording()
            if rec is not None:
                session = self.get_current_session()
                with self._lock:
                    session.add_recording(rec)
                    self._save_db()
                self._persist_project_recording(rec)

                # fan out
                for cb in list(self._on_record_end_callbacks):
                    try:
                        cb(rec)
                    except Exception as e:
                        logger.warning(f"on_record_end callback failed: {e}")
            # reset transient
            self._reset_transient()

    # ---- helpers ------------------------------------------------------------
    def _reset_transient(self) -> None:
        self._await_count_in = False
        self._t0_wall = None
        self._t1_wall = None
        self._rec_start_beats = None
        self._start_cue_path = ""
        self._stop_cue_path = ""
        self._start_combined_path = ""
        self._stop_combined_path = ""
        self._armed_track_names = []
        self._capture_this_take = True
        self._cues_this_take = True

    def _mark_start(self, s) -> None:
        self._await_count_in = False
        self._t0_wall = time.time()

        # capture musical snapshot at start
        self._rec_start_beats = float(getattr(s, "current_song_time", 0.0))
        self._rec_start_bpm = float(getattr(s, "tempo", self._rec_start_bpm))

        self._ts_num = int(getattr(s, "time_signature_numerator", 4))
        self._ts_den = int(getattr(s, "time_signature_denominator", 4))

        self._loop_start_b = float(getattr(s, "loop_start", 0.0))
        self._loop_len_b = float(getattr(s, "loop_length", 0.0))

        # snapshot currently armed tracks (names)
        try:
            self._armed_track_names = self._get_currently_armed_track_names()
        except Exception:
            self._armed_track_names = []

        logger.info(
            f" Record START @ beats={self._rec_start_beats:.3f}, "
            f"loop_start={self._loop_start_b:.3f}, loop_len={self._loop_len_b:.3f}, "
            f"bpm={self._rec_start_bpm:.2f}, ts={self._ts_num}/{self._ts_den}"
        )

        capture_enabled, cues_enabled = self._resolve_recording_flags()
        self._capture_this_take = capture_enabled
        self._cues_this_take = cues_enabled
        logger.info(
            "RecordingManager: starting take capture_enabled=%s cues_enabled=%s armed_tracks=%s",
            capture_enabled,
            cues_enabled,
            self._armed_track_names,
        )

        # Play START cues immediately when record starts if enabled
        if cues_enabled:
            try:
                self._play_on_start(s)
            except Exception as e:
                logger.warning(f"Start cue playback failed: {e}")
        else:
            logger.debug("Cue playback disabled for this project; skipping start cue.")

    def _compute_last_full_loop_bounds(self) -> Tuple[Optional[float], Optional[float], bool, bool]:
        """
        Returns:
          (rel_loop_start_sec, rel_loop_end_sec, took_at_least_one, took_at_least_two)
        based on snapshot at record start and t1 at record end.
        """
        if self._t0_wall is None or self._t1_wall is None or self._rec_start_beats is None:
            return None, None, False, False
        if self._loop_len_b <= 0:
            return None, None, False, False

        bpm = self._rec_start_bpm
        loop_sec = beats_to_seconds(self._loop_len_b, bpm)

        # phase (beats) inside loop at record start
        phase_b = (self._rec_start_beats - self._loop_start_b) % self._loop_len_b
        # time to NEXT loop boundary from t0
        delta_first_start_b = (self._loop_len_b - phase_b) % self._loop_len_b
        delta_first_start_s = beats_to_seconds(delta_first_start_b, bpm)

        t_first_start = self._t0_wall + delta_first_start_s
        t_first_end = t_first_start + loop_sec

        if self._t1_wall <= t_first_end:
            # no full loop completed
            return None, None, False, False

        # number of *completed* full loops after the first full loop
        n_full = math.floor((self._t1_wall - t_first_start) / loop_sec)
        took_at_least_one = n_full >= 1
        took_at_least_two = n_full >= 2

        # last full take boundaries
        t_last_end = t_first_start + n_full * loop_sec
        t_last_start = t_last_end - loop_sec

        rel_start = max(0.0, t_last_start - self._t0_wall)
        rel_end = max(0.0, t_last_end - self._t0_wall)
        return rel_start, rel_end, took_at_least_one, took_at_least_two

    def _persist_project_recording(self, recording: AbletonRecording) -> None:
        if self._recording_state_store is None:
            return
        folder = self._current_project_folder()
        if not folder:
            return
        try:
            self._recording_state_store.append_recording(folder, recording.model_dump(exclude_none=True))
        except Exception as exc:
            logger.warning("RecordingManager: failed to append recording to %s: %s", folder, exc)

    # ---- track snapshot helpers --------------------------------------------
    def _get_currently_armed_track_names(self) -> List[str]:
        names: List[str] = []
        try:
            song = getattr(self.client, "song", None) or self.client.get_song()
        except Exception:
            song = None
        tracks = []
        if song is not None:
            try:
                tracks = list(getattr(song, "tracks", []) or [])
            except Exception:
                tracks = []
        for tr in tracks:
            try:
                if bool(getattr(tr, "arm", False)):
                    nm = str(getattr(tr, "name", ""))
                    if nm:
                        names.append(nm)
            except Exception:
                continue
        return names

    def _build_recording(self) -> Optional[AbletonRecording]:
        if not getattr(self, "_capture_this_take", True):
            logger.debug("Recording capture disabled for this project; skipping this take.")
            return None
        logger.debug(
            "RecordingManager:_build_recording capture=%s cues=%s start=%s stop=%s",
            self._capture_this_take,
            self._cues_this_take,
            self._t0_wall,
            self._t1_wall,
        )
        try:
            # ensure armed track names exist
            if not getattr(self, "_armed_track_names", None):
                try:
                    self._armed_track_names = self._get_currently_armed_track_names()
                except Exception:
                    self._armed_track_names = []
            cue_dir = self._cue_storage_dir()
            # Ensure cue paths are available for this recording
            if not getattr(self, "_start_cue_path", "") and _legacy_ensure_refs is not None:
                try:
                    start_path, *_rest = _legacy_ensure_refs(ref_dir=str(cue_dir))
                    self._start_cue_path = str(start_path)
                except Exception:
                    pass
            if (
                not getattr(self, "_stop_cue_path", "")
                and not getattr(self, "_stop_combined_path", "")
                and (not getattr(self, "_cues_this_take", True))
                and 'ensure_stop_ref' in globals()
                and ensure_stop_ref is not None
            ):
                try:
                    suffix = self._timestamp_suffix(self._t1_wall or time.time())
                    stop_path, _ = ensure_stop_ref(filename=f"stop_{suffix}.wav", ref_dir=str(cue_dir))
                    self._stop_cue_path = str(stop_path)
                except Exception:
                    pass
            # Guarantee unique cue file references even if playback was disabled
            if self._start_cue_path:
                self._start_cue_path = self._ensure_unique_cue_reference(
                    self._start_cue_path,
                    "start",
                    cue_dir,
                    timestamp=self._t0_wall,
                )
            if self._stop_cue_path:
                self._stop_cue_path = self._ensure_unique_cue_reference(
                    self._stop_cue_path,
                    "stop",
                    cue_dir,
                    timestamp=self._t1_wall,
                )

            name = str(getattr(self.song, "name", "") or "")
            path = str(getattr(self.song, "file_path", "") or "")
            t0 = float(self._t0_wall or time.time())
            t1 = float(self._t1_wall or time.time())

            # bars
            bpb = beats_per_bar(self._ts_num, self._ts_den)
            start_bar = float(self._rec_start_beats or 0.0) / bpb
            # Approx end beats using constant BPM
            delta_sec = max(0.0, t1 - t0)
            end_beats = float(self._rec_start_beats or 0.0) + (delta_sec * self._rec_start_bpm / 60.0)
            end_bar = end_beats / bpb

            loop_start_bar = float(self._loop_start_b) / bpb
            loop_end_bar = loop_start_bar + (float(self._loop_len_b) / bpb)

            rel_loop_start, rel_loop_end, took_one, took_two = self._compute_last_full_loop_bounds()

            rec = AbletonRecording(
                project_name=name,
                file_path=path,
                takes_recorded=bool(took_one),
                multiple_takes=bool(took_two),
                start_recording_bar=start_bar,
                end_recording_bar=end_bar,
                loop_start_bar=loop_start_bar,
                loop_end_bar=loop_end_bar,
                time_start_recording=t0,
                time_end_recording=t1,
                time_loop_start=rel_loop_start,
                time_loop_end=rel_loop_end,
                bpm_at_start=self._rec_start_bpm,
                ts_num=self._ts_num,
                ts_den=self._ts_den,
                start_sound_path=self._start_combined_path or self._start_cue_path or "",
                end_sound_path=self._stop_combined_path or self._stop_cue_path or "",
                start_combined_path=self._start_combined_path or self._start_cue_path or "",
                end_combined_path=self._stop_combined_path or self._stop_cue_path or "",
                recording_track_names=list(self._armed_track_names or []),
            )

            # Log summary
            if took_one:
                logger.success(
                    " Recording captured  last full loop: "
                    f"{rel_loop_start:.3f}s  {rel_loop_end:.3f}s "
                    f"(takes: {'2' if took_two else '1'})"
                )
            else:
                logger.warning(" Recording captured  no full loop completed during the window.")
            return rec

        except Exception as e:
            logger.exception(f"Failed to build AbletonRecording: {e}")
            return None

    # ---- cue playback helpers ---------------------------------------------
    def _seed_from_ableton_time(self, beats: float, bpm: float) -> int:
        """Derive a stable 31-bit seed from Ableton song time and tempo."""
        b = int(abs(round((beats or 0.0) * 1000.0)))
        t = int(abs(round((bpm or 0.0) * 100.0)))
        seed = (b ^ (t << 1) ^ 0x9E3779B1) & 0x7FFFFFFF
        return seed if seed > 0 else 1

    # ---- file/time helpers for cue artifacts -------------------------------
    def _timestamp_suffix(self, t: float) -> str:
        import datetime
        dt = datetime.datetime.fromtimestamp(float(t))
        return dt.strftime("%Y%m%d_%H%M%S_%f")[:-3]  # up to milliseconds

    def _cue_storage_dir(self) -> Path:
        folder = self._current_project_folder()
        base = Path(folder) / "ableton" / "cue_refs" if folder else self._default_cue_dir
        base.mkdir(parents=True, exist_ok=True)
        return base

    def _ensure_unique_cue_reference(self, cue_path: str, prefix: str, cue_dir: Path, *, timestamp: float | None = None) -> str:
        if not cue_path:
            return cue_path
        path = Path(cue_path)
        if not path.exists():
            return cue_path
        name = path.name.lower()
        if name.startswith(f"{prefix}_"):
            return str(path)
        suffix = self._timestamp_suffix(timestamp or time.time())
        dst = cue_dir / f"{prefix}_{suffix}.wav"
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dst)
        return str(dst)

    def _save_stereo_pcm_wav(self, path: str, pcm_bytes: bytes, samplerate: int = 48000) -> None:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with wave.open(path, "wb") as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(int(samplerate))
            wf.writeframes(pcm_bytes)

    def _float_stereo_to_pcm(self, stereo: np.ndarray) -> bytes:
        arr = np.clip(stereo, -1.0, 1.0)
        return (arr * 32767).astype(np.int16).tobytes()

    def _unique_start_variant(self, stereo: np.ndarray, seed: int) -> np.ndarray:
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

    def _write_combined_cue(self, path: str, segments: List[np.ndarray], *, samplerate: int = 48000) -> float:
        if not segments:
            return 0.0
        data = np.concatenate([np.asarray(seg, dtype=np.float32) for seg in segments], axis=0)
        pcm = self._float_stereo_to_pcm(data)
        self._save_stereo_pcm_wav(path, pcm, samplerate=samplerate)
        duration = float(len(data)) / float(samplerate or 1)
        logger.info(
            "RecordingManager: wrote combined cue %s (%d frames @ %d Hz, %.3fs)",
            os.path.basename(path),
            len(data),
            samplerate,
            duration,
        )
        return duration

    def _play_on_start(self, s) -> None:
        if CuePlayer is None:
            return
        cp = CuePlayer.instance()
        segments: List[np.ndarray] = []
        if _legacy_ensure_refs is not None:
            try:
                cue_dir = self._cue_storage_dir()
                start_path, _end_path, start_f32, _end_f32, _start_pcm, _end_pcm = _legacy_ensure_refs(ref_dir=str(cue_dir))
                suffix = self._timestamp_suffix(self._t0_wall or time.time())
                dst_dir = os.path.dirname(start_path) or str(cue_dir)
                dst_path = os.path.join(dst_dir, f"start_{suffix}.wav")
                seed = int((self._t0_wall or time.time()) * 1000)
                unique_start = self._unique_start_variant(start_f32, seed)
                cp.play(unique_start)
                segments.append(np.array(unique_start, dtype=np.float32))

                barker = to_stereo(mk_barker_bpsk(chip_ms=18.0, carrier_hz=3200.0, fs=cp.fs_out)) * 1.2
                barker = np.clip(barker, -1.0, 1.0)
                cp.play(barker, samplerate=cp.fs_out)
                segments.append(np.array(barker, dtype=np.float32))

                beats = float(getattr(s, "current_song_time", self._rec_start_beats or 0.0))
                bpm = float(getattr(s, "tempo", self._rec_start_bpm))
                seed_val = self._seed_from_ableton_time(beats, bpm)
                seed_stereo = to_stereo(unique_cue(seed_val, length=START_SEED_LENGTH)) * START_SEED_GAIN
                seed_stereo = np.clip(seed_stereo, -1.0, 1.0)
                cp.play(seed_stereo)
                segments.append(np.array(seed_stereo, dtype=np.float32))

                if segments:
                    sr = int(getattr(cp, "fs_out", 48000) or 48000)
                    durations = [float(len(seg)) / float(sr) for seg in segments]
                    summary = (durations + [sum(durations)])[:4]
                    summary += [0.0] * (4 - len(summary))
                    logger.info(
                        "RecordingManager: start cue segments unique=%.3fs barker=%.3fs seed=%.3fs total=%.3fs",
                        *summary,
                    )
                    self._write_combined_cue(dst_path, segments, samplerate=sr)
                    self._start_cue_path = str(dst_path)
                    self._start_combined_path = str(dst_path)
            except Exception as e:
                logger.debug(f"Legacy start cue failed: {e}")

    def _play_on_stop(self, s=None) -> None:
        if CuePlayer is None:
            return
        playback_enabled = bool(getattr(self, "_cues_this_take", True))
        cp = CuePlayer.instance()
        segments: List[np.ndarray] = []
        primary_played = False
        if playback_enabled and _legacy_ensure_refs is not None:
            try:
                cue_dir = self._cue_storage_dir()
                (
                    _start_path,
                    end_path,
                    _start_f32,
                    _end_f32,
                    _start_pcm,
                    _end_pcm,
                ) = _legacy_ensure_refs(ref_dir=str(cue_dir))
                suffix = self._timestamp_suffix(self._t1_wall or time.time())
                dst_dir = os.path.dirname(end_path) or str(cue_dir)
                dst_path = os.path.join(dst_dir, f"stop_{suffix}.wav")
                seed = int((self._t1_wall or time.time()) * 1000)
                unique_end = to_stereo(mk_stop_unique(seed=seed))
                cp.play(unique_end)
                segments.append(np.array(unique_end, dtype=np.float32))

                barker = to_stereo(mk_barker_bpsk(chip_ms=18.0, carrier_hz=2400.0, fs=cp.fs_out)) * 1.2
                barker = np.clip(barker, -1.0, 1.0)
                cp.play(barker, samplerate=cp.fs_out)
                segments.append(np.array(barker, dtype=np.float32))

                beats = float(getattr(s or self.song, "current_song_time", 0.0))
                bpm = float(getattr(s or self.song, "tempo", self._rec_start_bpm))
                seed_val = self._seed_from_ableton_time(beats, bpm)
                seed_stereo = to_stereo(unique_cue(seed_val, length=STOP_SEED_LENGTH)) * STOP_SEED_GAIN
                seed_stereo = np.clip(seed_stereo, -1.0, 1.0)
                cp.play(seed_stereo)
                segments.append(np.array(seed_stereo, dtype=np.float32))

                if segments:
                    sr = int(getattr(cp, "fs_out", 48000) or 48000)
                    durations = [float(len(seg)) / float(sr) for seg in segments]
                    summary = (durations + [sum(durations)])[:4]
                    summary += [0.0] * (4 - len(summary))
                    logger.info(
                        "RecordingManager: stop cue segments unique=%.3fs barker=%.3fs seed=%.3fs total=%.3fs",
                        *summary,
                    )
                    self._write_combined_cue(dst_path, segments, samplerate=sr)
                    self._stop_cue_path = str(dst_path)
                    self._stop_combined_path = str(dst_path)
                primary_played = True
            except Exception as e:
                logger.debug(f"Legacy stop cue failed: {e}")
        if not primary_played and playback_enabled:
            try:
                cp.play_barker(chip_ms=18.0, carrier_hz=2400.0, gain=1.2, blocking=True)
            except Exception:
                pass
            try:
                src = s or self.song
                beats = float(getattr(src, "current_song_time", 0.0))
                bpm = float(getattr(src, "tempo", self._rec_start_bpm))
                seed = self._seed_from_ableton_time(beats, bpm)
                cp.play_seed(seed, dur=STOP_SEED_LENGTH, blocking=True, gain=STOP_SEED_GAIN)
            except Exception:
                pass
            if ensure_stop_ref is not None:
                try:
                    cue_dir = self._cue_storage_dir()
                    suffix = self._timestamp_suffix(self._t1_wall or time.time())
                    stop_path, _ = ensure_stop_ref(filename=f"stop_{suffix}.wav", ref_dir=str(cue_dir))
                    self._stop_cue_path = str(stop_path)
                    self._stop_combined_path = str(stop_path)
                except Exception as exc:
                    logger.debug(f"Fallback stop cue generation failed: {exc}")

    # ---- persistence --------------------------------------------------------
    def _load_db(self) -> _DBEnvelope:
        if not self.db_path.exists():
            return _DBEnvelope()
        try:
            raw = json.loads(self.db_path.read_text(encoding="utf-8"))
            return _DBEnvelope(**raw)
        except Exception as e:
            logger.warning(f"RecordingManager: failed to read DB, starting fresh. Error: {e}")
            return _DBEnvelope()

    def _save_db(self) -> None:
        tmp = self.db_path.with_suffix(".tmp")
        data = self._env.model_dump()  # enthlt datetime-Objekte

        def default(o):
            from datetime import datetime
            if isinstance(o, datetime):
                return o.isoformat()  # sauber lesbar & JSON-kompatibel
            return str(o)  # Fallback fr ObjectId, UUID etc.

        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=default), encoding="utf-8")
        tmp.replace(self.db_path)
        logger.debug(f" Saved local Ableton recordings DB  {self.db_path.name}")


    def _is_project_unsaved(self) -> bool:
        try:
            path = str(getattr(self.song, "file_path", "") or "")
            return not bool(path)
        except Exception:
            return True

    def _maybe_warn_unsaved_project(self) -> None:
        if not getattr(self, "_warned_unsaved_project", False) and self._is_project_unsaved():
            logger.warning("Please save your Ableton project before recording (no .als path detected).")
            self.warn_user_to_save_project()
            self._warned_unsaved_project = True

    def _derive_project_root(self, song_path: str) -> Optional[str]:
        if not song_path:
            return None
        resolved = Path(song_path).resolve()
        parts_lower = [part.lower() for part in resolved.parts]
        if "ableton" in parts_lower:
            idx = parts_lower.index("ableton")
            if idx > 0:
                root = Path(*resolved.parts[:idx])
                return str(root)
        try:
            # default: go up two levels (ableton/<project>/<als>)
            return str(resolved.parents[2])
        except IndexError:
            try:
                return str(resolved.parent)
            except Exception:
                return None

    def _current_project_folder(self) -> Optional[str]:
        try:
            path = str(getattr(self.song, "file_path", "") or "")
        except Exception:
            path = ""
        root = self._derive_project_root(path)
        if root:
            return root
        return str(Path(path).parent) if path else None

    def _resolve_recording_flags(self) -> Tuple[bool, bool]:
        """
        Returns (capture_enabled, cues_enabled) based on recordings.json state.
        Defaults to (True, True) when unavailable.
        """
        if self._recording_state_store is None:
            return True, True
        folder = self._current_project_folder()
        if not folder:
            return True, True
        try:
            state = self._recording_state_store.load(folder)
        except Exception as exc:
            logger.debug(f"RecordingManager: failed to load recording state for {folder}: {exc}")
            return True, True
        capture_enabled = bool(state.get("capture_enabled", state.get("cues_enabled", True)))
        cues_enabled = bool(state.get("cues_enabled", state.get("capture_enabled", True)))
        logger.debug(
            "RecordingManager: resolved state flags for %s (capture=%s cues=%s)",
            state.get("project_path"),
            capture_enabled,
            cues_enabled,
        )
        return capture_enabled, cues_enabled

    def warn_user_to_save_project(self):
        import ctypes
        MB_ICONWARNING = 0x30
        MB_OKCANCEL = 0x1

        message = (
            "[WARN] Please save your Ableton project before recording.\n\n"
            "Without a saved .als file path, Ableton Live will not be able to sync the recordings to MongoDB."
        )
        title = "Save Project First"

        result = ctypes.windll.user32.MessageBoxW(None, message, title, MB_OKCANCEL | MB_ICONWARNING)
        # result == 1  OK, result == 2  Cancel
        return result == 1
