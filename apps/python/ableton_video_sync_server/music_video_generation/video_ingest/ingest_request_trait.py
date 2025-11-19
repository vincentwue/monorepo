from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from ..core.trait_registry import registry


class IngestRequestTrait(BaseModel):
    """Represents a request to ingest media from one or more configured devices."""

    project_name: str = Field(..., description="Human readable project label typed by the user.")
    project_slug: str | None = Field(
        default=None,
        description="Slugified project identifier derived from the name (stable for folders).",
    )
    device_ids: list[str] = Field(
        default_factory=list,
        description="Idea IDs of ingest_device entries to pull from. Empty = use all active devices.",
    )
    only_today: bool = Field(
        default=True,
        description="If true, restrict ingest to files captured on the current day.",
    )
    status: Literal["pending", "running", "completed", "failed"] = Field(
        default="pending",
        description="Lifecycle state of the ingest run.",
    )
    output_dir: str | None = Field(
        default=None,
        description="Absolute path on disk where media was stored.",
    )
    copied_count: int = Field(default=0, description="Number of files copied during the ingest run.")
    copied_files: list[str] = Field(
        default_factory=list,
        description="List of copied file paths (relative to output_dir).",
    )
    error: str | None = Field(default=None, description="Error message when status='failed'.")
    started_at: str | None = Field(default=None, description="ISO timestamp when ingest began.")
    completed_at: str | None = Field(default=None, description="ISO timestamp when ingest finished.")


registry.register("ingest_request", IngestRequestTrait)
