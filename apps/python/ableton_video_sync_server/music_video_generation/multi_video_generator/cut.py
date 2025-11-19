import random
from dataclasses import dataclass
from typing import List, Optional
from .model import Video, VideoProject


@dataclass
class CutClip:
    time_global: float
    duration: float
    video: Video
    inpoint: float
    outpoint: float


class CutGenerator:
    def __init__(self, project: VideoProject):
        self.project = project

    @staticmethod
    def _durations_from_cuts(cuts: List[float], fallback_last: float) -> List[float]:
        if not cuts:
            return []
        durs = []
        for i in range(len(cuts) - 1):
            durs.append(max(0.0, cuts[i + 1] - cuts[i]))
        durs.append(max(0.0, fallback_last))
        return durs

    def generate_sequence(
        self,
        rng: Optional[random.Random] = None,
        last_clip_duration: Optional[float] = None,
    ) -> List[CutClip]:
        if not self.project.groups:
            raise ValueError("No video groups loaded.")

        rng = rng or random.Random()
        fallback = (
            last_clip_duration
            if last_clip_duration is not None
            else self.project.beat_seconds
        )
        durations = self._durations_from_cuts(self.project.cut_times, fallback)

        seq: List[CutClip] = []
        for t, dur in zip(self.project.cut_times, durations):
            group = rng.choice(self.project.groups)
            if not group.videos:
                continue
            video = rng.choice(group.videos)

            base_in = (video.sync_time or 0.0) + t
            inpoint = max(0.0, min(base_in, max(0.0, video.duration - 1e-3)))
            outpoint = min(video.duration, inpoint + dur)

            if outpoint - inpoint < 1e-2:
                continue

            seq.append(
                CutClip(
                    time_global=t,
                    duration=outpoint - inpoint,
                    video=video,
                    inpoint=inpoint,
                    outpoint=outpoint,
                )
            )
        return seq
