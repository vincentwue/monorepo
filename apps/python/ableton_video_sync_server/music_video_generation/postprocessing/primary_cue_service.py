from __future__ import annotations

import sys
from pathlib import Path

# We want to use the monorepo version of cue_detection_service, not a pip-installed one.
# Layout:
#   <REPO_ROOT>/
#       packages/
#           python/
#               cue_detection_service/
#                   __init__.py
#                   primary.py
#
# This file lives at:
#   <REPO_ROOT>/apps/python/ableton_video_sync_server/music_video_generation/postprocessing/primary_cue_service.py
#
# So parents[6] = <REPO_ROOT>

REPO_ROOT = Path(__file__).resolve().parents[6]
PKG_ROOT = REPO_ROOT / "packages" / "python"

# Ensure our monorepo packages are searched first.
for p in (PKG_ROOT, REPO_ROOT):
    sp = str(p)
    if sp not in sys.path:
        # Insert at the front to outrank site-packages.
        sys.path.insert(0, sp)

# Now this will resolve to <REPO_ROOT>/packages/python/cue_detection_service/primary.py
from cue_detection_service.primary import PrimaryCueDetectionService  # type: ignore[import]

__all__ = ["PrimaryCueDetectionService"]
