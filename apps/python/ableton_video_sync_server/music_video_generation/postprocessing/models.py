from datetime import datetime
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field


class AbletonSegment(BaseModel):
    index: int
    start_time_s: float
    end_time_s: Optional[float] = None
    duration_s: Optional[float] = None
    edge_case: Optional[str] = None


class AbletonPostprocessingFields(BaseModel):
    file_path: str
    duration_s: Optional[float]
    segments: List[AbletonSegment]
    cue_refs_used: List[str]
    processed_at: datetime = Field(default_factory=datetime.utcnow)


class AbletonPostprocessingIdea(BaseModel):
    tags: List[str] = ["ableton", "postprocessing"]
    traits: List[str] = ["ableton_postprocessing"]
    metadata: Dict[str, Any] = {}
    fields: Dict[str, AbletonPostprocessingFields]
