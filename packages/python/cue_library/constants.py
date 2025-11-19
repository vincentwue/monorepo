from __future__ import annotations

DEFAULT_SAMPLE_RATE = 48_000
DEFAULT_FADE_MS = 8
DEFAULT_REF_DIR = "cue_refs"
DEFAULT_PEAK_DB = -1.0


def db_to_linear(db_value: float) -> float:
    return 10 ** (db_value / 20.0)


__all__ = [
    "DEFAULT_SAMPLE_RATE",
    "DEFAULT_FADE_MS",
    "DEFAULT_REF_DIR",
    "DEFAULT_PEAK_DB",
    "db_to_linear",
]
