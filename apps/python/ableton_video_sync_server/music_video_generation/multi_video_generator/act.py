import os
import random
import subprocess
from typing import List, Dict, Optional, Tuple

# from playground.multi_video_generator.video_ingest.cli import ingest_videos_main
from playground.multi_video_generator.model import VideoGroup, Video
from playground.multi_video_generator.cut import CutClip
from playground.multi_video_generator.ffmpeg_render import FFmpegRenderer
from packages.playground.src.playground.multi_video_generator.helper import (
    build_zero_sync_map,
)
from playground.multi_video_generator.sync.postprocess_recordings import postprocess_recordings

CUT_AUDIO_NAME = "cut_audio.mp3"
try:
    from mutagen import File as MutagenFile  # optional Fallback
except Exception:
    MutagenFile = None


AUDIO_EXTS = (".mp3", ".m4a", ".aac", ".wav")


class Act:
    def __init__(
        self,
        root: str,
        project_name: str,
        bpm: float,
        cuts=None,
        song_len_sec: float = None,
        beats_per_bar: int = 4,
        bars_step: float = 1.0,
        last_clip_duration: float | None = None,
        seed: int = 42,
        sync_times_per_group=None,
        align_mode: str = "cut_time",
        start_offset: float = 0.0,
        debug: bool = True,
        time_signature: Tuple[int, int] = (4, 4),
    ):
        self.debug = debug
        self.bpm = float(bpm)
        self.beats_per_bar = int(beats_per_bar)
        self.bars_step = float(bars_step)
        self.start_offset = float(start_offset)
        self.align_mode = align_mode
        self.seed = int(seed)
        self.time_signature = time_signature

        self.root = root
        self.current_project = project_name
        self.project_path = os.path.join(root, project_name)
        self.footage_path = os.path.join(self.project_path, "footage")
        self.videos_path = os.path.join(self.footage_path, "videos")
        self.music_path = os.path.join(self.footage_path, "music")
        self.images_path = os.path.join(self.footage_path, "images")
        self.out_path = os.path.join(self.project_path, "generated")
        os.makedirs(self.out_path, exist_ok=True)

        # --- Falls song_len_sec fehlt: aus Musikdatei ermitteln
        if song_len_sec is None:
            music_file = self._find_first_music_file()
            if music_file is None:
                raise RuntimeError(
                    f"Keine Musikdatei in {self.music_path} gefunden, "
                    "kann song_len_sec nicht automatisch bestimmen."
                )
            try:
                song_len_sec = self._probe_audio_duration(music_file)
            except Exception as e:
                raise RuntimeError(
                    f"Konnte Dauer nicht aus {music_file} bestimmen: {e}"
                ) from e

        self.song_len_sec = float(song_len_sec)
        self.time_signature = time_signature
        print(f"Song-Dauer: {song_len_sec:.2f}s")

        # --- Cuts vorbereiten (entweder bernommen oder aus BPM vorab berechnet)
        self.cuts = (
            list(cuts)
            if cuts is not None
            else precalc_bpm_cuts(
                bpm=self.bpm,
                song_len_sec=self.song_len_sec,
                beats_per_bar=self.beats_per_bar,
                bars_step=self.bars_step,
                start_offset=self.start_offset,
                nominator=self.time_signature[0],
                include_zero=False,
            )
        )

        # Dauer des letzten Clips
        self.last_clip_duration = (
            float(last_clip_duration)
            if last_clip_duration is not None
            else (60.0 / self.bpm)
        )

        # Zero-Sync-Map bauen und ggf. mergen
        auto_zero_map: Dict[str, Dict[str, float]] = {}
        try:
            auto_zero_map = build_zero_sync_map(self.project_path)
        except Exception as e:
            print(f"[WARN] auto-build zero sync map failed: {e}")

        self.sync_times_per_group = _deep_merge_sync_maps(
            auto_zero_map, sync_times_per_group or {}
        )

        # Gruppen laden
        self.groups: List[VideoGroup] = []
        self.load_groups()

        # Reproduzierbarkeit
        random.seed(self.seed)

    # ----- Helpers -----

    def _find_first_music_file(self) -> Optional[str]:
        """Erste passende Audiodatei im Musikordner finden."""
        if not os.path.isdir(self.music_path):
            return None
        for name in sorted(os.listdir(self.music_path)):

            if name.lower().endswith(AUDIO_EXTS) and not CUT_AUDIO_NAME == name:
                return os.path.join(self.music_path, name)
        return None

    def _probe_audio_duration(self, path: str) -> float:
        """
        Dauer der Audiodatei in Sekunden bestimmen:
        1) ffprobe (falls vorhanden)
        2) Mutagen (Fallback, wenn installiert)
        """
        # ffprobe: sehr robust, deckt mp3/m4a/aac/wav ab
        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=nw=1:nk=1",
                    path,
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            val = result.stdout.strip()
            if val and val.upper() != "N/A":
                dur = float(val)
                if dur > 0:
                    return dur
        except Exception:
            pass  # weiter zu Mutagen

        # Mutagen Fallback (falls installiert)
        if MutagenFile is not None:
            audio = MutagenFile(path)
            if audio is not None and getattr(audio, "info", None):
                dur = float(getattr(audio.info, "length", 0.0) or 0.0)
                if dur > 0:
                    return dur

        raise RuntimeError(
            "Weder ffprobe verfgbar noch Mutagen konnte eine Dauer liefern."
        )

    def _beat_seconds(self) -> float:
        return 60.0 / self.bpm

    def _bar_seconds(self) -> float:
        return self.beats_per_bar * self._beat_seconds()


    def _auto_cut_times(self) -> List[float]:
        """Cuts im Raster von bars_step Bars bis song_len_sec."""


        step = self.bars_step * self._bar_seconds()
        t = 0.0
        cuts: List[float] = []
        while t < (self.song_len_sec + self.start_offset_sec) and t < self.max_audio_dur:
            cuts.append(round(t, 6))
            t += step
        return cuts
    @property
    def start_offset_sec(self):
        return (60.0 / self.bpm * self.time_signature[0]) * self.start_offset
    # ----- IO -----

    def load_groups(self):
        """Rekursiv Unterordner als Videogruppen laden (jede Map in sync_times_per_group anwenden)."""
        if not os.path.isdir(self.footage_path):
            print(f"[WARN] footage path not found: {self.footage_path}")
            return
        for root, dirs, files in os.walk(self.footage_path):
            video_files = [
                f for f in files if f.lower().endswith((".mp4", ".mov", ".mkv")) and "seg" in f
            ]
            if video_files:
                group_name = os.path.basename(root)
                sync_map = self.sync_times_per_group.get(group_name, {})
                self.groups.append(VideoGroup(root, sync_map=sync_map))

        if not self.groups:
            print("[WARN] no video groups detected under footage/")

    # ----- Core -----

    def get_cut_times(self) -> List[float]:
        return list(self.cuts) if self.cuts is not None else self._auto_cut_times()

    def generate_cut_sequence(self, cut_args=None) -> List[Dict]:
        """
        Fr jede Cut-Zeit:
          - zufllige Gruppe & Video whlen
          - Inpoint gem align_mode berechnen
        Rckgabe: Liste von Dicts {time, video, start_time_in_video}
        """
        cut_times = self.get_cut_times()
        if not self.groups:
            raise RuntimeError("No video groups loaded.")

        cut_sequence: List[Dict] = []
        for t in cut_times:
            group = random.choice(self.groups)
            tries = 0
            while not getattr(group, "videos", None) and tries < len(self.groups):
                group = random.choice(self.groups)
                tries += 1
            if not getattr(group, "videos", None):
                continue

            video: Video = random.choice(group.videos)

            if self.align_mode == "cut_time":
                inpoint = float(t)
            else:  # "sync_plus_cut"
                inpoint = (video.sync_time or 0.0) + float(t)

            cut_sequence.append(
                {"time": float(t), "video": video, "start_time_in_video": float(inpoint)}
            )
        return cut_sequence

    def render_random_edit(self, output_file: str, resolution: Tuple[int, int] = (1920, 1080), fps=30, audio_source=None) -> str:
        seq_dicts = self.generate_cut_sequence()

        self.max_audio_dur = self._probe_audio_duration(audio_source)
        # Clip-Dauern aus Cut-Abstnden + last_clip_duration
        cuts = [d["time"] for d in seq_dicts]
        durations = []
        for i in range(len(cuts) - 1):
            durations.append(max(0.0, cuts[i + 1] - cuts[i]))
        durations.append(self.last_clip_duration)

        seq_clips: List[CutClip] = []
        for dct, dur in zip(seq_dicts, durations):
            v: Video = dct["video"]
            ip = float(dct["start_time_in_video"])
            # clamp in/out
            ip = max(0.0, min(ip, max(0.0, v.duration - 1e-3)))
            op = min(v.duration, ip + dur)
            if op - ip >= 1e-2:
                seq_clips.append(
                    CutClip(
                        time_global=dct["time"],
                        duration=op - ip,
                        video=v,
                        inpoint=ip,
                        outpoint=op,
                    )
                )

        renderer = FFmpegRenderer(debug=self.debug, width=resolution[0], height=resolution[1], fps=fps)
        os.makedirs(os.path.dirname(output_file), exist_ok=True)

        # Musikdatei auswhlen (gleiche Logik wie oben)
        music_file = audio_source or self._find_first_music_file()
        cut_music_file = self.get_cut_audio_source(music_file, out_file=CUT_AUDIO_NAME, start_offset=self.start_offset_sec, nominator=self.time_signature[0])
        if not music_file:
            raise RuntimeError("No music files found in music folder.")

        return renderer.render_sequence(
            seq_clips, os.path.abspath(output_file), audio_source=cut_music_file
        )

    def get_cut_audio_source(self, music_file=None, out_file=CUT_AUDIO_NAME, start_offset=0.0, nominator=4):
        if music_file is None:
            music_file = self._find_first_music_file()
        if not music_file:
            raise RuntimeError("No music files found in music folder.")

        # Sekunden-Offset berechnen
        t0 = start_offset

        # Ausgabepfad im Projekt
        out_path = os.path.join(self.out_path, out_file)

        # ffmpeg-Befehl: schneide ab t0
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(t0),  # Startzeit
            "-i", music_file,  # Input
            "-c", "copy",  # kein Re-encode, nur cut
            out_path
        ]
        subprocess.run(cmd, check=True)

        return out_path

def _deep_merge_sync_maps(
    base: Dict[str, Dict[str, float]], override: Dict[str, Dict[str, float]]
) -> Dict[str, Dict[str, float]]:
    """Merge per-group sync maps. Values in 'override' take precedence."""
    out = {k: dict(v) for k, v in base.items()}
    for g, m in (override or {}).items():
        if g not in out:
            out[g] = dict(m)
        else:
            out[g].update(m or {})
    return out


def precalc_bpm_cuts(
    bpm: float,
    song_len_sec: float,
    *,
    beats_per_bar: int = 4,
    bars_step: float = 1.0,
    start_offset: float = 0.0,
    include_zero: bool = True,
    round_to_ms: float = 0.01,
    nominator: int = 4,
) -> List[float]:
    """Return cut times aligned to bars given BPM."""
    if bpm <= 0:
        raise ValueError("bpm must be > 0")
    if song_len_sec <= 0:
        return []

    beat = 60.0 / bpm
    bar = beats_per_bar * beat
    step = max(bar * bars_step, 1e-6)

    start_offset_sec = (60.0 / bpm * nominator) * start_offset
    start_offset = start_offset_sec

    t0 = max(start_offset, 0.0)
    # print(f"start_offset_sec: {start_offset_sec}, include_zero: {include_zero}, t0: {t0}, start_offset_sec: {start_offset_sec}")
    t = 0.0 if include_zero and t0 == 0 else t0
    cuts: List[float] = []
    # ensure first cut at t0, then step forward
    while t <= song_len_sec - 1e-6 + start_offset_sec: # TODO upper bound
        r = round(t / round_to_ms) * round_to_ms
        if not cuts or abs(r - cuts[-1]) >= round_to_ms / 2:
            cuts.append(r)
        t = (t if t >= t0 else t0) + step if cuts else t0

    cuts = [c for c in cuts if 0.0 <= c < (song_len_sec + start_offset_sec)]
    cuts = sorted(dict.fromkeys(cuts))
    return cuts
