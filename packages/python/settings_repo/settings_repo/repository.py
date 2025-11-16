from __future__ import annotations

from datetime import datetime
from typing import Any

from db_core import get_db
from permissions import (
    build_object_id,
    keto_write,
    require_user_permission,
    user_subject,
)
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from .models import IdeaTreeUiState, UserSettingsDocument

COLLECTION_NAME = "user_settings"
SETTINGS_NAMESPACE = "app:ideas"
_SETTINGS_KIND = "idea_tree_settings"


def _collection():
    return get_db()[COLLECTION_NAME]


def _object_id(workspace_id: str) -> str:
    return build_object_id(SETTINGS_NAMESPACE, _SETTINGS_KIND, workspace_id)


async def _ensure_permissions(user_id: str, workspace_id: str) -> None:
    subject = user_subject(user_id)
    object_id = _object_id(workspace_id)
    for relation in ("viewer", "editor"):
        await keto_write(
            namespace=SETTINGS_NAMESPACE,
            object=object_id,
            relation=relation,
            subject=subject,
        )


async def _require(workspace_id: str, user_id: str, relation: str) -> None:
    await _ensure_permissions(user_id, workspace_id)
    await require_user_permission(
        namespace=SETTINGS_NAMESPACE,
        kind=_SETTINGS_KIND,
        resource_id=workspace_id,
        relation=relation,
        user_id=user_id,
    )


def _doc_to_model(doc: dict[str, Any]) -> UserSettingsDocument:
    payload = {
        "user_id": doc.get("user_id") or doc.get("_id"),
        "idea_tree": doc.get("idea_tree") or {},
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }
    return UserSettingsDocument.model_validate(payload)


async def get_user_settings(workspace_id: str, user_id: str) -> UserSettingsDocument:
    await _require(workspace_id, user_id, "viewer")
    collection = _collection()
    doc = await collection.find_one({"_id": workspace_id})
    if not doc:
        now = datetime.utcnow()
        state = IdeaTreeUiState()
        record = {
            "_id": workspace_id,
            "user_id": workspace_id,
            "idea_tree": state.model_dump(),
            "created_at": now,
            "updated_at": now,
        }
        try:
            await collection.insert_one(record)
            return UserSettingsDocument(
                user_id=workspace_id,
                idea_tree=state,
                created_at=now,
                updated_at=now,
            )
        except DuplicateKeyError:
            doc = await collection.find_one({"_id": workspace_id})
            if doc:
                return _doc_to_model(doc)
            raise
    return _doc_to_model(doc)


async def upsert_idea_tree_state(
    workspace_id: str,
    user_id: str,
    idea_tree_state: IdeaTreeUiState,
) -> UserSettingsDocument:
    await _require(workspace_id, user_id, "editor")
    collection = _collection()
    now = datetime.utcnow()
    doc = await collection.find_one_and_update(
        {"_id": workspace_id},
        {
            "$set": {
                "user_id": workspace_id,
                "idea_tree": idea_tree_state.model_dump(),
                "updated_at": now,
            },
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    if not doc:
        doc = {
            "_id": workspace_id,
            "user_id": workspace_id,
            "idea_tree": idea_tree_state.model_dump(),
            "created_at": now,
            "updated_at": now,
        }
    return _doc_to_model(doc)
