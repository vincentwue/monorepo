from pathlib import Path

MONGO_URI = "mongodb://localhost:27025"
DB_NAME = "vincent_core"
COLL_NAME = "ableton.postprocessing"

INPUT_PATH = Path(r"D:\git_repos\todos\server\var\media_ingest\5-euro-kopfh-rer")
REF_DIR = Path(r"D:\git_repos\todos\cue_refs")

FS = 48000
THRESHOLD = 0.6  # instead of 0.9
MIN_GAP_S = 0.25
FADE_MS = 8
