# ableton_last_full_take.py
from __future__ import annotations
import time, math
from typing import Optional, Dict, Callable
from loguru import logger
from server.src.libraries_to_port.m22.src.m22.music22_settings_dir.live_rpyc.live_client import LiveClient

def beats_to_seconds(b: float, bpm: float) -> float:
    return 0.0 if bpm <= 0 else (60.0 / bpm) * b

class LastFullLoopTake:
    """Compute last full loop take using loop_start/loop_length at record start/end."""
    def __init__(self, on_take: Optional[Callable[[Dict], None]] = None):
        self.client = LiveClient.get_instance()
        self.song = self.client.get_song()

        # recording window (wall clock)
        self.t0_wall: Optional[float] = None
        self.t1_wall: Optional[float] = None

        # snapshots at record start (beats)
        self.rec_start_beats: Optional[float] = None
        self.rec_start_bpm: float = float(self.song.tempo)

        # loop params (beats) read when needed
        self.loop_start_b: float = float(getattr(self.song, "loop_start", 0.0))
        self.loop_len_b: float   = float(getattr(self.song, "loop_length", 0.0))

        # count-in handling
        self._await_count_in = False

        self.on_take = on_take
        self._register()

    # ----------------- listeners -----------------
    def _register(self):
        c = self.client
        c.on_record_mode(lambda s: self._on_record_mode(s))
        c.on_is_counting_in(lambda s: self._on_count_in(s))

    def _on_count_in(self, s):
        if self._await_count_in and not s.is_counting_in:
            self._mark_start(s)

    def _on_record_mode(self, s):
        if s.record_mode:
            # record turned ON
            self._await_count_in = bool(getattr(s, "is_counting_in", False))
            if self._await_count_in:
                logger.info(" Record ON  waiting for count-in to finish...")
            else:
                self._mark_start(s)
        else:
            # record turned OFF
            if self.t0_wall is None:
                # safety fallback
                self._mark_start(s)
            self.t1_wall = time.time()
            logger.info(" Record OFF.")
            self._emit_last_full_take()

    # ----------------- start/end snapshots -----------------
    def _mark_start(self, s):
        self._await_count_in = False
        self.t0_wall = time.time()
        self.rec_start_beats = float(s.current_song_time)  # beats
        self.rec_start_bpm   = float(s.tempo)
        # read loop params once at start (you said: just check loop start/end and compute)
        self.loop_start_b = float(s.loop_start)
        self.loop_len_b   = float(s.loop_length)
        logger.info(
            f" Record START @ beats={self.rec_start_beats:.3f}, "
            f"loop_start={self.loop_start_b:.3f}, loop_len={self.loop_len_b:.3f}, "
            f"bpm={self.rec_start_bpm:.2f}"
        )

    # ----------------- core computation -----------------
    def _emit_last_full_take(self):
        if self.t0_wall is None or self.t1_wall is None or self.rec_start_beats is None:
            logger.warning("Recording window incomplete  cannot compute take.")
            return
        if self.loop_len_b <= 0:
            logger.warning("Loop length is zero  no full take possible.")
            return

        # constants (assume constant tempo over the window)
        bpm = self.rec_start_bpm
        loop_dur_sec = beats_to_seconds(self.loop_len_b, bpm)

        # phase at record start (beats inside the loop window)
        # cs should be within [loop_start, loop_start + loop_len), but we mod just in case
        phase_b = (self.rec_start_beats - self.loop_start_b) % self.loop_len_b
        # time to NEXT loop boundary (i.e., next loop start) after t0, in beats/sec
        delta_first_start_b = (self.loop_len_b - phase_b) % self.loop_len_b
        delta_first_start_s = beats_to_seconds(delta_first_start_b, bpm)

        # first full take window after record start, in wall time
        t_first_start = self.t0_wall + delta_first_start_s
        t_first_end   = t_first_start + loop_dur_sec

        if self.t1_wall <= t_first_end:
            logger.warning("No full loop completed within the recording window.")
            return

        # how many full loops fit until record end?
        n_full = math.floor((self.t1_wall - t_first_start) / loop_dur_sec)
        # last full take end/start (wall time)
        t_last_end   = t_first_start + n_full * loop_dur_sec
        t_last_start = t_last_end   - loop_dur_sec

        # relative seconds from record start
        rel_start_sec = max(0.0, t_last_start - self.t0_wall)
        rel_end_sec   = max(0.0, t_last_end   - self.t0_wall)

        # relative beats from record start (using bpm at start)
        rel_start_beats = rel_start_sec * bpm / 60.0
        rel_end_beats   = rel_end_sec   * bpm / 60.0

        payload = {
            "bpm_at_start": bpm,
            "loop_start_beats": self.loop_start_b,
            "loop_length_beats": self.loop_len_b,
            "rel_start_sec": rel_start_sec,
            "rel_end_sec": rel_end_sec,
            "rel_start_beats": rel_start_beats,
            "rel_end_beats": rel_end_beats,
            "duration_sec": rel_end_sec - rel_start_sec,
        }

        logger.success(
            " LAST FULL LOOP TAKE (relative to record start)  "
            f"start={rel_start_sec:.3f}s  end={rel_end_sec:.3f}s  "
            f"dur={payload['duration_sec']:.3f}s  "
            f"[beats {rel_start_beats:.3f}  {rel_end_beats:.3f}]"
        )
        if self.on_take:
            try:
                self.on_take(payload)
            except Exception as e:
                logger.warning(f"on_take callback failed: {e}")

# ---- quick CLI usage ----
if __name__ == "__main__":
    logger.remove()
    logger.add(lambda m: print(m, end=""), level="INFO",
               format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>\n")
    _ = LastFullLoopTake(on_take=lambda p: None)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
