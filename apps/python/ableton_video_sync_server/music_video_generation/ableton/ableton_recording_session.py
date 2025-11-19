from __future__ import annotations
from typing import List
from pydantic import BaseModel, Field
from datetime import datetime
import uuid

from .ableton_recording import AbletonRecording


class AbletonRecordingSession(BaseModel):
    """Represents the current Live Set context (project) and all its recordings."""
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_name: str = Field(default="", description="Live Set name (empty if unsaved).")
    file_path: str = Field(default="", description="Live Set path (empty if unsaved).")
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat(timespec="seconds") + "Z")

    recordings: List[AbletonRecording] = Field(default_factory=list)

    def add_recording(self, rec: AbletonRecording) -> None:
        self.recordings.append(rec)

