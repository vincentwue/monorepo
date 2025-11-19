from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from ..core.trait_registry import registry


class AvailableDeviceSnapshot(BaseModel):
    """Snapshot of a currently detected ingest-capable device (focus on Android ADB)."""

    kind: Literal["adb"] = Field(default="adb", description="Transport kind; currently only adb is supported.")
    serial: str = Field(..., description="ADB serial reported by the device.")
    label: str = Field(..., description="Human-friendly display label (model or alias).")
    connection_state: Literal["ready", "needs_permission", "offline", "unknown"] = Field(
        default="unknown",
        description="Aggregated connection status derived from adb state.",
    )
    status_text: str = Field(
        default="Waiting for device status",
        description="Short string shown to the user explaining the current status.",
    )
    hints: list[str] = Field(
        default_factory=list,
        description="Optional suggestions to resolve the state (e.g. enable debugging).",
    )
    model: str | None = Field(default=None, description="Reported Android model name.")
    product: str | None = Field(default=None, description="ADB product identifier.")
    device: str | None = Field(default=None, description="ADB device codename.")
    transport_id: str | None = Field(default=None, description="ADB transport id when available.")
    registered_device_id: str | None = Field(
        default=None,
        description="Idea id of the configured ingest_device entry matching this serial, if any.",
    )
    configured_path: str | None = Field(
        default=None,
        description="Path currently configured on the ingest_device idea (useful to prefill the UI).",
    )
    last_seen_at: str | None = Field(
        default=None,
        description="ISO timestamp when this serial was last seen in a ready state.",
    )


class DirectoryEntrySnapshot(BaseModel):
    """Directory entry (folder) available on a connected Android device."""

    path: str = Field(..., description="Absolute remote path to the directory.")
    name: str = Field(..., description="Display name extracted from the path.")


class DirectoryListingSnapshot(BaseModel):
    """Result of browsing a directory on a connected Android device."""

    serial: str = Field(..., description="ADB serial of the device these entries belong to.")
    path: str = Field(..., description="Absolute path that was queried.")
    parent: str | None = Field(
        default=None,
        description="Parent directory path, if navigable within the allowed roots.",
    )
    entries: list[DirectoryEntrySnapshot] = Field(
        default_factory=list,
        description="Immediate child directories under the requested path.",
    )


class DirectoryBrowseRequest(BaseModel):
    """Request payload for browsing directories on an Android device."""

    serial: str = Field(..., description="ADB serial of the target device.")
    path: str | None = Field(
        default=None,
        description="Optional path to browse; defaults to the primary DCIM location when omitted.",
    )


class IngestDeviceDiscoveryTrait(BaseModel):
    """Collection of currently available ingest devices detected via the ingest connector."""

    adb_available: bool = Field(
        default=False,
        description="True when the adb executable is reachable on the server.",
    )
    adb_error: str | None = Field(
        default=None,
        description="Optional diagnostic message describing why adb is unavailable.",
    )
    last_scanned_at: str | None = Field(
        default=None,
        description="ISO timestamp of the most recent discovery scan.",
    )
    devices: list[AvailableDeviceSnapshot] = Field(
        default_factory=list,
        description="Per-device snapshots available for rendering the ingest UI.",
    )
    directory_request: DirectoryBrowseRequest | None = Field(
        default=None,
        description="Latest directory browse request issued by the UI (processed on refresh).",
    )
    directory_listing: DirectoryListingSnapshot | None = Field(
        default=None,
        description="Latest directory listing result returned from the device browse request.",
    )


registry.register("ingest_device_discovery", IngestDeviceDiscoveryTrait)

__all__ = [
    "AvailableDeviceSnapshot",
    "DirectoryEntrySnapshot",
    "DirectoryListingSnapshot",
    "DirectoryBrowseRequest",
    "IngestDeviceDiscoveryTrait",
]
