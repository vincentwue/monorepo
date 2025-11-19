#!/usr/bin/env python3
"""
Mongo writer for Ableton postprocessing results
-----------------------------------------------
Inserts detection summaries into:
    db = vincent_core
    collection = ableton.postprocessing

Each document mirrors the "idea" schema used elsewhere,
but stores fields specific to audio/video cue detection.
"""

from pymongo import MongoClient
from pathlib import Path
from datetime import datetime
import petname

from .models import AbletonPostprocessingIdea, AbletonPostprocessingFields, AbletonSegment
from .config import DB_NAME, COLL_NAME


def generate_petname_id(prefix: str = "postproc") -> str:
    """
    Generate a human-readable idea-style ID like:
        postproc-happy-otter-2048
    """
    base = petname.Generate(2, separator="-")  # e.g. "happy-otter"
    digits = str(datetime.utcnow().microsecond % 10000).zfill(4)
    return f"{prefix}-{base}-{digits}"


def insert_postprocessing_result(client: MongoClient, res: dict):
    """
    Insert a single postprocessing result into MongoDB.
    Creates a unique, human-readable _id using petnames.
    """
    db = client[DB_NAME]
    coll = db[COLL_NAME]

    # Build nested field models
    fields = AbletonPostprocessingFields(
        file_path=res["file"],
        duration_s=res.get("duration_s"),
        segments=[AbletonSegment(**s) for s in res.get("segments", [])],
        cue_refs_used=res.get("cue_refs_used", []),
    )

    # 🆕 unique idea-style ID
    idea_id = generate_petname_id()

    # Assemble the full idea document
    idea = AbletonPostprocessingIdea(
        _id=idea_id,
        title=f"Postprocessing {Path(res['file']).stem}",
        summary=f"{len(fields.segments)} segments detected",
        fields={"ableton_postprocessing": fields},
        metadata={
            "source_file": res["file"],
            "processed_at": fields.processed_at.isoformat(),
            "notes": res.get("notes", []),
        },
    )

    # Convert to dict and insert
    doc = idea.model_dump(by_alias=True)
    coll.insert_one(doc)

    print(f"✅ Inserted {idea_id} → {DB_NAME}.{COLL_NAME}")
