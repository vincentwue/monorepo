from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from ..core.trait_registry import registry


DeviceKind = Literal["filesystem", "adb"]


class IngestDeviceTrait(BaseModel):
    """Configuration trait for ingest devices (phones, cameras, removable storage)."""

    device_name: str = Field(..., description="Human friendly label (e.g. Pixel 8, Lumix).")
    kind: DeviceKind = Field(
        default="filesystem",
        description="Ingest strategy: 'filesystem' for mounted media, 'adb' for Android devices.",
    )
    path: str = Field(..., description="Path or remote directory to scan for media.")
    adb_serial: str | None = Field(
        default=None,
        description="Optional ADB serial when kind='adb'; required if multiple phones are connected.",
    )
    active: bool = Field(default=True, description="Flag to include device in automatic ingest runs.")
    preferred_globs: list[str] = Field(
        default_factory=lambda: [
            "DCIM/**/*.mp4",
            "DCIM/**/*.mov",
            "DCIM/**/*.jpg",
            "DCIM/**/*.png",
        ],
        description="File patterns (relative to path) that should be imported.",
    )
    last_seen_at: str | None = Field(
        default=None,
        description="Timestamp (ISO) when the device was last detected as connected.",
    )
    last_import_at: str | None = Field(
        default=None,
        description="Timestamp (ISO) when a successful ingest completed for this device.",
    )


registry.register("ingest_device", IngestDeviceTrait)
