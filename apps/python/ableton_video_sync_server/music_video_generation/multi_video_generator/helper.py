# build_zero_sync_map.py
import json
import os
from pathlib import Path
from typing import Dict, Iterable

VIDEO_EXTS = {".mp4", ".mov", ".mkv"}


def list_videos_sorted(folder: Path, exts: Iterable[str] = VIDEO_EXTS):
    """Liste Videodateien alphabetisch (case-insensitive) sortiert."""
    files = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in exts and "seg" in p.name]
    return sorted(files, key=lambda p: p.name.lower())


def build_zero_sync_map(project_root: str) -> Dict[str, Dict[str, float]]:
    """
    Erwartet Projektstruktur:
      <project_root>/
        footage/
          phone_marco/
          phone_vincent/
          lumix/
    Liefert: { group_name: { video_name (ohne Endung): 0.0, ... }, ... }
    """
    project_root = Path(project_root)
    footage = project_root / "footage" / "videos"
    # groups = ["phone_marco", "phone_vincent", "lumix"]
    groups = os.listdir(footage)

    sync_map: Dict[str, Dict[str, float]] = {}
    for g in groups:
        gpath = footage / g
        if not gpath.is_dir():
            # print(f"[WARN] Gruppe fehlt oder ist kein Ordner: {gpath}")
            continue

        vids = list_videos_sorted(gpath)
        if not vids:
            print(f"[INFO] keine Videos gefunden in: {gpath}")
            continue

        # Video-Key = Basename ohne Endung -> passt zu Video.name
        sync_map[g] = {v.stem: 0.0 for v in vids}

        # Optional: kurzer Report
        print(f"[OK] {g} -> {len(vids)} Videos: {[v.name for v in vids]}")

    return sync_map


if __name__ == "__main__":
    # Beispiel: passe den Pfad an dein Projekt an
    PROJECT_PATH = r"D:\Workspace tmp\cobra"  # enthlt 'footage\phone_marco', 'footage\phone_vincent', 'footage\lumix'
    sync_map = build_zero_sync_map(PROJECT_PATH)

    # hbsch ausgeben
    print("\n=== sync_times_per_group ===")
    print(json.dumps(sync_map, indent=2, ensure_ascii=False))
