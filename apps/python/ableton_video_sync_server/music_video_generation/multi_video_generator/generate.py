# playground/multi_video_generator/run_main.py

import os
import random
from typing import List, Optional, Dict

from .model import VideoProject
from .cut import CutGenerator
from .ffmpeg_render import FFmpegRenderer

ROOT = os.path.join(r"D:\Workspace tmp\current_project")


def generate_cut_times_from_bpm(
    bpm: float,
    song_len_sec: float,
    beats_per_bar: int = 4,
    bars_step: float = 0.5,
) -> List[float]:
    """
    Erzeugt Cut-Zeitpunkte automatisch:
    - alle 'bars_step' Takte (z.B. 0.5 = halbe Takte) bis song_len_sec
    - 1 Takt = beats_per_bar * (60 / bpm) Sekunden
    """
    beat_sec = 60.0 / bpm
    bar_sec = beats_per_bar * beat_sec
    t, cuts = 0.0, []
    step = bars_step * bar_sec
    while t < song_len_sec:
        cuts.append(round(t, 6))
        t += step
    return cuts


def apply_sync_times_from_map(
    project: VideoProject,
    sync_times_per_group: Dict[str, Dict[str, float]] | Dict[str, float] | None,
):
    """
    Setzt optional sync_time:
    - Variante A (pro Video): { "GroupName": { "VideoName": 2.3, ... }, ... }
    - Variante B (pro Gruppe): { "GroupName": 2.3, ... } -> gilt fr alle Videos der Gruppe
    """
    if not sync_times_per_group:
        return

    for g in project.groups:
        entry = sync_times_per_group.get(g.name)
        if entry is None:
            continue
        if isinstance(entry, dict):
            # pro Video
            g.set_sync_times({k: float(v) for k, v in entry.items()})
        else:
            # pro Gruppe: gleicher Wert fr alle Videos
            value = float(entry)
            g.set_sync_times({v.name: value for v in g.videos})


def run_job(
    root: str,
    bpm: float,
    out_path: str,
    cuts: Optional[List[float]] = None,
    # Auto-Cuts (falls cuts=None):
    song_len_sec: Optional[float] = None,
    beats_per_bar: int = 4,
    bars_step: float = 0.5,
    # Sonstiges:
    last_clip_duration: Optional[float] = None,
    seed: Optional[int] = None,
    # Optional Sync:
    sync_times_per_group: Dict[str, Dict[str, float]] | Dict[str, float] | None = None,
):
    """
    Fhrt die komplette Pipeline ohne CLI aus:
    - Projekt laden
    - (optional) sync_time setzen
    - Cuts definieren (explizit oder automatisch)
    - Zufllige Sequenz generieren
    - ProRes rendern (Auflsung unverndert)
    """
    project = VideoProject(root_folder=root, bpm=bpm, cut_times=[])
    project.load_groups()
    project.ensure_sync_times_set()

    # Optional: sync_time setzen
    apply_sync_times_from_map(project, sync_times_per_group)

    # Cuts: explizit oder automatisch
    if cuts is not None:
        project.cut_times = list(cuts)
    else:
        if song_len_sec is None:
            raise ValueError(
                "Entweder 'cuts' angeben ODER 'song_len_sec' fr Auto-Cuts setzen."
            )
        project.cut_times = generate_cut_times_from_bpm(
            bpm=bpm,
            song_len_sec=song_len_sec,
            beats_per_bar=beats_per_bar,
            bars_step=bars_step,
        )

    # Sequenz erzeugen
    gen = CutGenerator(project)
    rng = random.Random(seed) if seed is not None else random.Random()
    seq = gen.generate_sequence(rng=rng, last_clip_duration=last_clip_duration)

    # Rendern
    renderer = FFmpegRenderer(
        prores_profile=3,  # ProRes 422 HQ
        pix_fmt="yuv422p10le",
        audio_codec="pcm_s16le",
        reencode=True,
    )
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    result = renderer.render_sequence(seq, os.path.abspath(out_path))
    print(f"[OK] Fertig: {result}")


class Act:
    def __init__(self):
        self.current_project = "cobra"
        self.project_path = os.path.join(ROOT, self.current_project)
        self.footage_path = os.path.join(self.project_path, "footage")
        self.videos_path = os.path.join(self.project_path, "videos")
        self.music_path = os.path.join(self.project_path, "music")
        self.images_path = os.path.join(self.project_path, "images")
        self.OUT = os.path.join(self.project_path, "generated")


if __name__ == "__main__":
    # =========== KONFIG ===========

    BPM = 120.0

    # --- Variante 1: Explizite Cut-Times ---
    CUTS: Optional[List[float]] = [0.0, 1.5, 3.0, 4.5, 6.0, 7.0, 8.0]
    # CUTS = None  # auskommentieren, wenn du Auto-Cuts (Variante 2) nutzen willst

    # --- Variante 2: Auto-Cuts aus BPM ---
    SONG_LEN_SEC = 60.0  # Lnge des Songs in Sekunden (nur wenn CUTS=None)
    BEATS_PER_BAR = 4  # Taktart
    BARS_STEP = 4  # alle halben Takte schneiden (0.5 = halbe, 1.0 = ganze Takte)

    # --- Letzter Clip ---
    LAST_CLIP_DUR = None  # None => Standard = 60/BPM Sekunden

    # --- Reproduzierbarkeit ---
    SEED = 42

    # --- Optional: sync_time-Map ---
    # Variante A (pro Video):  {"GroupName": {"VideoName": 2.3, "VideoName2": 1.1}, ...}
    # Variante B (pro Gruppe): {"GroupName": 2.3, "AndereGruppe": 0.0}
    SYNC_MAP = {
        # "CamA": {"CamA_take1": 2.3, "CamA_take2": 1.1},
        # "CamB": 0.0,
    }

    # ========= AUSFHRUNG =========
    run_job(
        root=ROOT,
        bpm=BPM,
        out_path=OUT,
        cuts=CUTS,
        song_len_sec=SONG_LEN_SEC,
        beats_per_bar=BEATS_PER_BAR,
        bars_step=BARS_STEP,
        last_clip_duration=LAST_CLIP_DUR,
        seed=SEED,
        sync_times_per_group=SYNC_MAP,
    )
