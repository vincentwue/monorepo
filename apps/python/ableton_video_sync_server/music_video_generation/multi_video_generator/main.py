#!/usr/bin/env python3
"""
CLI entry point for the music video generation pipeline.

Usage examples:

    # Run cue detection + Mongo sync
    python -m music_video_generation.multi_video_generator.main postprocess

    # Render a sync edit using Mongo cue data
    python -m music_video_generation.multi_video_generator.main sync \\
        "My Project" D:/audio/export.mp3

    # Execute the full pipeline end-to-end
    python -m music_video_generation.multi_video_generator.main full \\
        "My Project" D:/videos D:/audio/export.mp3
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

from .pipeline import (
    match_export_to_recording,
    render_auto_bar_edit,
    render_sync_edit,
    run_full_pipeline,
    run_postprocessing,
)


def _print_json(payload: Dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def _add_common_pipeline_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--input-path", type=Path, help="Override media input path for cue detection")
    parser.add_argument("--ref-dir", type=Path, help="Override cue reference directory")
    parser.add_argument("--mongo-uri", type=str, help="MongoDB URI override")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="music-video-pipeline", description="Music video generation pipeline CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_post = sub.add_parser("postprocess", help="Detect cues and store segments in MongoDB")
    _add_common_pipeline_args(p_post)

    p_match = sub.add_parser("match-export", help="Attach an audio export to its Ableton recording")
    p_match.add_argument("audio_path", type=Path, help="Ableton export file (MP3/WAV)")
    p_match.add_argument("--mongo-uri", type=str, help="MongoDB URI override")

    p_sync = sub.add_parser("sync", help="Render tempo-synced multi-camera edit from Mongo segments")
    p_sync.add_argument("project_name", type=str, help="Ableton project name")
    p_sync.add_argument("audio_path", type=Path, help="Master audio track (MP3/WAV)")
    p_sync.add_argument("--bars-per-cut", type=int, help="Override bars per cut")
    p_sync.add_argument("--cut-length", type=float, help="Override cut length in seconds")
    p_sync.add_argument("--custom-duration", type=float, help="Force output duration in seconds")
    p_sync.add_argument("--debug", action="store_true", help="Enable verbose FFmpeg logging")

    p_auto = sub.add_parser("auto-bar", help="Render automatic bar-based edit")
    p_auto.add_argument("project_name", type=str, help="Ableton project name")
    p_auto.add_argument("video_dir", type=Path, help="Directory containing camera clips")
    p_auto.add_argument("audio_path", type=Path, help="Master audio track")
    p_auto.add_argument("--bars-per-cut", type=int, help="Override bars per cut")
    p_auto.add_argument("--custom-duration", type=float, help="Force output duration in seconds")

    p_full = sub.add_parser("full", help="Run the full pipeline end-to-end")
    p_full.add_argument("project_name", type=str, help="Ableton project name")
    p_full.add_argument("video_dir", type=Path, help="Directory containing camera clips")
    p_full.add_argument("audio_path", type=Path, help="Master audio track")
    _add_common_pipeline_args(p_full)
    p_full.add_argument("--match-audio", type=Path, help="Audio export to use for matching (defaults to audio_path)")
    p_full.add_argument("--bars-per-cut", type=int, help="Override bars per cut")
    p_full.add_argument("--cut-length", type=float, help="Override cut length in seconds")
    p_full.add_argument("--custom-duration", type=float, help="Force output duration in seconds")
    p_full.add_argument("--skip-postprocess", action="store_true", help="Skip cue detection step")
    p_full.add_argument("--skip-match", action="store_true", help="Skip export matching step")
    p_full.add_argument("--skip-sync", action="store_true", help="Skip sync edit rendering")
    p_full.add_argument("--skip-auto", action="store_true", help="Skip auto bar edit rendering")

    args = parser.parse_args(argv)

    try:
        if args.command == "postprocess":
            result = run_postprocessing(
                input_path=args.input_path,
                ref_dir=args.ref_dir,
                mongo_uri=args.mongo_uri,
            )
        elif args.command == "match-export":
            result = match_export_to_recording(
                args.audio_path,
                mongo_uri=args.mongo_uri,
            )
        elif args.command == "sync":
            result = render_sync_edit(
                args.project_name,
                args.audio_path,
                bars_per_cut=args.bars_per_cut,
                cut_length_s=args.cut_length,
                custom_duration_s=args.custom_duration,
                debug=args.debug,
            )
        elif args.command == "auto-bar":
            result = render_auto_bar_edit(
                args.project_name,
                args.video_dir,
                args.audio_path,
                bars_per_cut=args.bars_per_cut,
                custom_duration_s=args.custom_duration,
            )
        elif args.command == "full":
            result = run_full_pipeline(
                args.project_name,
                args.video_dir,
                args.audio_path,
                input_path=args.input_path,
                ref_dir=args.ref_dir,
                match_audio_path=args.match_audio,
                bars_per_cut=args.bars_per_cut,
                cut_length_s=args.cut_length,
                custom_duration_s=args.custom_duration,
                mongo_uri=args.mongo_uri,
                skip_postprocess=args.skip_postprocess,
                skip_match=args.skip_match,
                skip_sync=args.skip_sync,
                skip_auto=args.skip_auto,
            )
        else:  # pragma: no cover - argparse ensures this won't happen
            parser.error(f"Unsupported command: {args.command}")
            return 1
    except FileNotFoundError as exc:
        parser.error(str(exc))
        return 1
    except Exception as exc:  # pragma: no cover - report unexpected errors
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    _print_json(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
