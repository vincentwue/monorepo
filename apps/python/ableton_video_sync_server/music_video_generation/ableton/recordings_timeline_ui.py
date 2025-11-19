from __future__ import annotations

import argparse
import html
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional


@dataclass
class TimelineConfig:
    summary_path: Path
    output_path: Path
    title: str = "Cue Timeline Debugger"


def _format_seconds(value: Optional[float]) -> str:
    if value is None:
        return "—"
    return f"{value:.3f}s"


def _to_percent(value: Optional[float], total: float) -> float:
    if total <= 0 or value is None:
        return 0.0
    return max(0.0, min(100.0, (value / total) * 100.0))


def _segment_width(start: Optional[float], end: Optional[float], assumed_end: Optional[float], total: float) -> float:
    start_pct = _to_percent(start, total)
    if end is None and assumed_end is None:
        return max(1.5, 100.0 - start_pct)
    stop = end if end is not None else assumed_end
    stop_pct = _to_percent(stop, total)
    width = max(1.5, stop_pct - start_pct)
    max_width = max(1.5, 100.0 - start_pct)
    return min(width, max_width)


def _marker_title(event: dict) -> str:
    label = event.get("event_type", event.get("label", ""))
    time_s = event.get("time_s")
    refs = ", ".join(event.get("ref_ids") or [])
    max_score = event.get("max_score")
    hits = event.get("hits") or []
    detail = f"{label} at {_format_seconds(time_s)}"
    if max_score is not None:
        detail += f" | score: {max_score:.3f}"
    if refs:
        detail += f" | refs: {refs}"
    detail += f" | hits: {len(hits)}"
    return detail


def _segment_title(segment: dict) -> str:
    label = f"Segment {segment.get('index', '?')}"
    start = _format_seconds(segment.get("start_time_s"))
    end = _format_seconds(segment.get("end_time_s"))
    assumed = _format_seconds(segment.get("assumed_end_time_s"))
    duration = _format_seconds(segment.get("duration_s"))
    notes: List[str] = []
    if segment.get("edge_case"):
        notes.append(f"edge: {segment['edge_case']}")
    if segment.get("loop_footage"):
        notes.append("loop footage")
    if segment.get("end_time_s") is None and segment.get("assumed_end_time_s") is not None:
        notes.append(f"assumed end {assumed}")
    suffix = f" | duration {duration}"
    if notes:
        suffix += " | " + ", ".join(notes)
    return f"{label}: {start} → {end}{suffix}"


def _load_summary(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"Expected list at root of {path}, got {type(data)}")
    return data


def _build_html(entries: Iterable[dict], title: str) -> str:
    css = """
    body { font-family: "Segoe UI", Arial, sans-serif; background: #0f1015; color: #f2f4f8; margin: 24px; }
    h1 { font-size: 22px; margin-bottom: 24px; }
    .file-block { margin-bottom: 48px; padding: 20px; border-radius: 10px; background: #1b1d25; box-shadow: 0 8px 18px rgba(0,0,0,0.35); max-width: 1100px; }
    .file-title { font-size: 16px; font-weight: 600; margin-bottom: 6px; }
    .file-subtitle { font-size: 12px; color: #9aa0b5; margin-bottom: 16px; }
    .timeline { position: relative; height: 42px; margin-bottom: 12px; }
    .timeline .base { position: absolute; top: 18px; left: 0; right: 0; height: 6px; border-radius: 3px; background: linear-gradient(90deg, #394260, #6f7dff40); }
    .marker { position: absolute; top: 6px; width: 3px; bottom: 6px; border-radius: 2px; }
    .marker.start { background: #4caf50; }
    .marker.end { background: #f44336; }
    .marker.orphan { background: #ffb74d; }
    .marker::after { position: absolute; top: -18px; left: -14px; width: 32px; font-size: 10px; text-align: center; color: #f2f4f8; }
    .legend { font-size: 12px; color: #9aa0b5; margin-bottom: 12px; display: flex; gap: 16px; }
    .legend span { display: flex; align-items: center; gap: 6px; }
    .legend .swatch { width: 12px; height: 4px; border-radius: 2px; display: inline-block; }
    .segments { border-top: 1px solid rgba(255,255,255,0.05); padding-top: 14px; }
    .segment-row { position: relative; margin-bottom: 12px; padding-left: 4px; }
    .segment-bar { position: relative; height: 14px; border-radius: 7px; background: #2196f3; opacity: 0.8; }
    .segment-bar.loop { background: #ab47bc; }
    .segment-bar.edge { background: #ff7043; }
    .segment-label { font-size: 12px; color: #d0d4e4; margin-top: 4px; }
    .notes, .orphan-list { font-size: 12px; color: #ffb74d; margin-top: 8px; padding-left: 20px; }
    .empty { font-size: 12px; color: #9aa0b5; }
    """
    html_parts = [
        "<!DOCTYPE html>",
        "<html lang='en'>",
        "<head>",
        f"<meta charset='utf-8'/>",
        f"<title>{html.escape(title)}</title>",
        f"<style>{css}</style>",
        "</head>",
        "<body>",
        f"<h1>{html.escape(title)}</h1>",
        "<div class='legend'>"
        "<span><span class='swatch' style='background:#4caf50'></span> START</span>"
        "<span><span class='swatch' style='background:#f44336'></span> END</span>"
        "<span><span class='swatch' style='background:#ab47bc'></span> Loop footage</span>"
        "<span><span class='swatch' style='background:#ff7043'></span> Edge case</span>"
        "<span><span class='swatch' style='background:#ffb74d'></span> Orphan end</span>"
        "</div>",
    ]

    for entry in entries:
        file_path = entry.get("file") or "unknown"
        duration = entry.get("duration_s") or entry.get("waveform_duration_s") or 0.0
        total = duration if duration and duration > 0 else entry.get("waveform_duration_s") or 0.0
        total = float(total)
        segments = entry.get("segments") or []
        start_events = entry.get("start_events") or []
        end_events = entry.get("end_events") or []
        orphan_events = entry.get("orphan_end_events") or []
        notes = entry.get("notes") or []
        error = entry.get("error")
        skipped = entry.get("skipped")

        html_parts.append("<div class='file-block'>")
        html_parts.append(
            f"<div class='file-title'>{html.escape(file_path)}</div>"
        )

        subtitle_bits: List[str] = []
        subtitle_bits.append(f"analysis duration: {_format_seconds(duration)}")
        subtitle_bits.append(f"waveform: {_format_seconds(entry.get('waveform_duration_s'))}")
        if error:
            subtitle_bits.append(f"error: {html.escape(str(error))}")
        if skipped:
            subtitle_bits.append(f"skipped: {html.escape(str(skipped))}")
        html_parts.append(f"<div class='file-subtitle'>{' • '.join(subtitle_bits)}</div>")

        if error or skipped:
            html_parts.append("<div class='empty'>No visualization available.</div>")
            html_parts.append("</div>")
            continue

        html_parts.append("<div class='timeline'>")
        html_parts.append("<div class='base'></div>")

        for event in start_events:
            left = _to_percent(event.get("time_s"), total)
            title_attr = html.escape(_marker_title(event))
            html_parts.append(
                f"<div class='marker start' style='left:{left:.3f}%' title='{title_attr}'></div>"
            )
        for event in end_events:
            left = _to_percent(event.get("time_s"), total)
            title_attr = html.escape(_marker_title(event))
            html_parts.append(
                f"<div class='marker end' style='left:{left:.3f}%' title='{title_attr}'></div>"
            )
        for event in orphan_events:
            left = _to_percent(event.get("time_s"), total)
            title_attr = html.escape(_marker_title(event))
            html_parts.append(
                f"<div class='marker end orphan' style='left:{left:.3f}%' title='{title_attr}'></div>"
            )

        html_parts.append("</div>")  # timeline

        if segments:
            html_parts.append("<div class='segments'>")
            for segment in segments:
                left = _to_percent(segment.get("start_time_s"), total)
                width = _segment_width(
                    segment.get("start_time_s"),
                    segment.get("end_time_s"),
                    segment.get("assumed_end_time_s"),
                    total,
                )
                classes = ["segment-bar"]
                if segment.get("loop_footage"):
                    classes.append("loop")
                if segment.get("edge_case"):
                    classes.append("edge")
                class_attr = " ".join(classes)
                title_attr = html.escape(_segment_title(segment))
                html_parts.append("<div class='segment-row'>")
                html_parts.append(
                    f"<div class='{class_attr}' style='margin-left:{left:.3f}%; width:{width:.3f}%;' title='{title_attr}'></div>"
                )
                html_parts.append(
                    f"<div class='segment-label'>{html.escape(_segment_title(segment))}</div>"
                )
                html_parts.append("</div>")
            html_parts.append("</div>")
        else:
            html_parts.append("<div class='empty'>No segments detected.</div>")

        if notes:
            note_items = "".join(f"<li>{html.escape(str(n))}</li>" for n in notes)
            html_parts.append(f"<ul class='notes'>{note_items}</ul>")

        if orphan_events:
            orphan_items = "".join(
                f"<li>{html.escape(_marker_title(evt))}</li>" for evt in orphan_events
            )
            html_parts.append(f"<ul class='orphan-list'>{orphan_items}</ul>")

        html_parts.append("</div>")  # file block

    html_parts.append("</body></html>")
    return "\n".join(html_parts)


def render_summary_to_html(config: TimelineConfig) -> Path:
    entries = _load_summary(config.summary_path)
    html_content = _build_html(entries, config.title)
    config.output_path.write_text(html_content, encoding="utf-8")
    return config.output_path


def parse_args() -> TimelineConfig:
    parser = argparse.ArgumentParser(description="Render cue detection timelines for Ableton recordings.")
    parser.add_argument(
        "--summary",
        type=Path,
        required=True,
        help="Path to cue_timestamp_summary.json generated by postprocess_recordings.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Destination HTML file for the visualization. Defaults to <summary>.html",
    )
    parser.add_argument(
        "--title",
        type=str,
        default="Cue Timeline Debugger",
        help="Page title for the rendered report.",
    )
    args = parser.parse_args()
    summary_path = args.summary
    if not summary_path.exists():
        raise SystemExit(f"Summary file not found: {summary_path}")
    output_path = args.output or summary_path.with_suffix(".html")
    return TimelineConfig(summary_path=summary_path, output_path=output_path, title=args.title)


def main() -> None:
    config = parse_args()
    output = render_summary_to_html(config)
    print(f"Timeline UI written to {output}")


if __name__ == "__main__":
    main()
