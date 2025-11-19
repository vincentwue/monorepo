import argparse
import os
import random

from .model import VideoProject
from .cut import CutGenerator
from .ffmpeg_render import FFmpegRenderer


def main():
    p = argparse.ArgumentParser(
        description="Random Multi-Video Generator (ProRes, Auflsung unverndert)"
    )
    p.add_argument(
        "--root", required=True, help="Root-Ordner mit Unterordnern als VideoGroups"
    )
    p.add_argument("--bpm", type=float, required=True, help="Beats per minute")
    p.add_argument(
        "--cuts",
        type=float,
        nargs="+",
        required=True,
        help="Cut-Zeiten in Sekunden (global)",
    )
    p.add_argument(
        "--out", required=True, help="Zieldatei (z.B. converted/compilation.mp4)"
    )
    p.add_argument("--seed", type=int, default=None, help="Optional: RNG Seed")
    p.add_argument(
        "--last-dur",
        type=float,
        default=None,
        help="Dauer des letzten Clips (Sek.). Default: 60/BPM",
    )
    args = p.parse_args()

    project = VideoProject(root_folder=args.root, bpm=args.bpm, cut_times=args.cuts)
    project.load_groups()
    project.ensure_sync_times_set()

    # Beispiel: Sync-Times kannst du separat setzen, z.B. per JSON -> project.groups[i].set_sync_times(map)

    gen = CutGenerator(project)
    rng = random.Random(args.seed) if args.seed is not None else random.Random()
    seq = gen.generate_sequence(rng=rng, last_clip_duration=args.last_dur)

    renderer = FFmpegRenderer(
        prores_profile=3, pix_fmt="yuv422p10le", audio_codec="pcm_s16le", reencode=True
    )
    out_path = os.path.abspath(args.out)
    result = renderer.render_sequence(seq, out_path)
    print(f"[OK] Fertig: {result}")


if __name__ == "__main__":
    main()
