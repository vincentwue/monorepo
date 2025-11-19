from __future__ import annotations
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime


class AbletonRecording(BaseModel):
    """
    One 'press REC -> press STOP' event captured from Ableton Live.
    Times:
      - time_start_recording / time_end_recording are UNIX epoch seconds.
      - time_loop_start / time_loop_end are RELATIVE seconds (from record start) for the LAST FULL LOOP TAKE.
        If no full loop completed during the window, these are None.
    Bars:
      - start/end/loop_*_bar are in bars (float), computed from beats and time signature at record start.
    """
    # session context (duplicated for convenience/filtering)
    project_name: str = Field(default="")
    file_path: str = Field(default="")

    # status
    takes_recorded: bool = Field(..., description="True if at least one full loop take completed during the recording.")
    multiple_takes: bool = Field(..., description="True if at least two full loop takes completed during the recording.")

    # bars (float)
    start_recording_bar: float
    end_recording_bar: float
    loop_start_bar: float
    loop_end_bar: float

    # absolute wallclock times (epoch seconds)
    time_start_recording: float
    time_end_recording: float

    # last full loop take boundaries relative to record start (seconds)
    time_loop_start: Optional[float] = None
    time_loop_end: Optional[float] = None

    # useful metadata captured at start
    bpm_at_start: float
    ts_num: int = Field(..., description="Time signature numerator at record start")
    ts_den: int = Field(..., description="Time signature denominator at record start")
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat(timespec="seconds") + "Z")

    # start/end cue artifact paths
    start_sound_path: str = Field(default="")
    end_sound_path: str = Field(default="")

    recording_track_names : List[str] = Field(default_factory=list)

    class Config:
        arbitrary_types_allowed = True

