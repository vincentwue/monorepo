from __future__ import annotations

from typing import Dict, List

from .models import VideoSource


def make_adb_sources(serial_to_name: Dict[str, str], camera_path: str) -> List[VideoSource]:
    sources: list[VideoSource] = []
    for serial, name in serial_to_name.items():
        sources.append(
            VideoSource(
                path=camera_path,
                device_name=name,
                kind="adb",
                adb_serial=serial,
            )
        )
    return sources


__all__ = ["make_adb_sources"]
