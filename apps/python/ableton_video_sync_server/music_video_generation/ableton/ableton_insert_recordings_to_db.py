from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Dict

from bson import ObjectId
from loguru import logger
from pymongo import MongoClient
from pymongo.errors import PyMongoError

from server.src.config.settings import settings
from server.src.db.id_utils import generate_petname_id
from server.src.models.idea import Idea
from music_video_generation.ableton.ableton_recording import AbletonRecording


_IDEAS_CLIENT: MongoClient | None = None


def _get_ideas_collection():
    global _IDEAS_CLIENT
    if _IDEAS_CLIENT is None:
        uri = settings.mongo_uri_ideas or settings.mongo_uri
        _IDEAS_CLIENT = MongoClient(uri)
        logger.success(f"[AbletonRecording] Connected to ideas MongoDB @ {uri}")
    db_ideas = _IDEAS_CLIENT[settings.mongo_db_ideas]
    return db_ideas[settings.coll_ideas]


def _to_recording_payload(data: AbletonRecording | Dict[str, Any]) -> Dict[str, Any]:
    if isinstance(data, AbletonRecording):
        return data.model_dump(exclude_none=True)
    if isinstance(data, dict):
        payload = {**data}
        if "_id" in payload and not isinstance(payload["_id"], ObjectId):
            payload.pop("_id")
        return payload
    raise TypeError(f"Unsupported Ableton recording payload: {type(data)!r}")


def _parse_created_at(value: str | None) -> datetime:
    if not value:
        return datetime.now(UTC)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(UTC)


def _ensure_unique_id(coll, attempted: set[str] | None = None) -> str:
    attempted = attempted or set()
    for _ in range(1000):
        candidate = generate_petname_id(attempted)
        exists = coll.count_documents({"_id": candidate}, limit=1)
        if not exists:
            return candidate
    raise RuntimeError("Unable to allocate unique idea identifier for Ableton recording.")


def insert_ableton_recording(data: AbletonRecording | Dict[str, Any]):
    """
    Persist an Ableton recording as an idea under the configured parent.
    """
    collection = _get_ideas_collection()
    payload = _to_recording_payload(data)

    created_dt = _parse_created_at(payload.get("created_at"))
    project_name = payload.get("project_name") or "Ableton Recording"
    duration = None
    try:
        start_ts = float(payload.get("time_start_recording", 0.0))
        end_ts = float(payload.get("time_end_recording", start_ts))
        duration = max(0.0, end_ts - start_ts)
    except (TypeError, ValueError):
        start_ts = float(created_dt.timestamp())
        end_ts = start_ts
        duration = None

    timestamp_label = created_dt.strftime("%Y-%m-%d %H:%M:%S")
    title = f"{project_name} @ {timestamp_label}"
    summary_chunks = []
    if duration is not None:
        summary_chunks.append(f"{duration:.1f}s")
    if payload.get("bpm_at_start"):
        summary_chunks.append(f"{payload['bpm_at_start']} BPM")
    if payload.get("takes_recorded"):
        summary_chunks.append("with takes" if payload.get("multiple_takes") else "single take")
    summary = " | ".join(summary_chunks) if summary_chunks else "Captured Ableton recording."

    metadata = {
        "project_name": payload.get("project_name"),
        "file_path": payload.get("file_path"),
        "imported_at": datetime.now(UTC),
        "time_start_recording": payload.get("time_start_recording"),
        "time_end_recording": payload.get("time_end_recording"),
        "duration_seconds": duration,
    }

    trait_name = settings.ableton_recording_trait
    rank = float(payload.get("time_start_recording") or created_dt.timestamp())
    idea_tags = settings.ableton_recording_tag_list

    idea = Idea(
        id=_ensure_unique_id(collection),
        type="idea",
        parent_id=settings.ableton_recordings_parent_id or None,
        rank=rank,
        title=title,
        summary=summary,
        tags=idea_tags,
        traits=[trait_name],
        fields={trait_name: payload},
        metadata=metadata,
    )
    idea.created_at = created_dt
    idea.updated_at = created_dt

    doc = idea.model_dump(by_alias=True)

    try:
        collection.insert_one(doc)
        logger.success(
            "Inserted Ableton recording idea (id={}, project={}, duration={})",
            doc["_id"],
            project_name,
            f"{duration:.1f}s" if duration is not None else "unknown",
        )
        return str(doc["_id"])
    except PyMongoError as exc:
        logger.error("Failed to insert Ableton recording idea: {}", exc)
        raise RuntimeError(f"Mongo insert failed: {exc}") from exc
