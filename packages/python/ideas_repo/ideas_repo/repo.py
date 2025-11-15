"""Async persistence layer for ideas along with permission enforcement."""

from __future__ import annotations

from typing import List, Optional
from uuid import uuid4

from db_core import get_db
from permissions import build_object_id, keto_write, require_user_permission, user_subject

from .errors import IdeaNotFoundError
from .models import IdeaCreate, IdeaNode, IdeaUpdate

IDEAS_NAMESPACE = "app:ideas"
COLLECTION_NAME = "ideas"
ROOT_ID = "ROOT"
_KIND = "node"
_ROOT_OBJECT_ID = build_object_id(IDEAS_NAMESPACE, _KIND, ROOT_ID)


async def _ensure_root_permissions(user_id: str) -> None:
    """
    Ensure the requesting user has the default viewer/editor permissions
    on their personal root node so first-time access succeeds.
    """

    subject = user_subject(user_id)
    for relation in ("viewer", "editor"):
        await keto_write(
            namespace=IDEAS_NAMESPACE,
            object=_ROOT_OBJECT_ID,
            relation=relation,
            subject=subject,
        )


def _resource_id(node_id: Optional[str]) -> str:
    return node_id or ROOT_ID


def _collection():
    return get_db()[COLLECTION_NAME]


def _doc_to_model(doc: dict) -> IdeaNode:
    return IdeaNode(
        id=str(doc.get("_id") or doc["id"]),
        parent_id=doc.get("parent_id"),
        title=doc["title"],
        note=doc.get("note"),
        rank=float(doc.get("rank", 0)),
        owner_id=doc["owner_id"],
    )


async def list_children_for_user(
    user_id: str,
    parent_id: Optional[str],
) -> List[IdeaNode]:
    """List child nodes visible to the user under the provided parent."""

    if parent_id is None:
        await _ensure_root_permissions(user_id)

    await require_user_permission(
        namespace=IDEAS_NAMESPACE,
        kind=_KIND,
        resource_id=_resource_id(parent_id),
        relation="viewer",
        user_id=user_id,
    )

    collection = _collection()
    cursor = (
        collection.find({"parent_id": parent_id, "owner_id": user_id})
        .sort("rank", 1)
    )

    docs = [doc async for doc in cursor]
    return [_doc_to_model(doc) for doc in docs]


async def _next_rank(user_id: str, parent_id: Optional[str]) -> float:
    collection = _collection()
    cursor = (
        collection.find({"parent_id": parent_id, "owner_id": user_id})
        .sort("rank", -1)
        .limit(1)
    )
    docs = await cursor.to_list(length=1)
    if docs:
        return float(docs[0].get("rank", 0)) + 1
    return 0.0


async def create_child_for_user(
    user_id: str,
    parent_id: Optional[str],
    title: str,
    note: Optional[str] = None,
) -> IdeaNode:
    """Create a child node and append it to the end of the sibling list."""

    if parent_id is None:
        await _ensure_root_permissions(user_id)

    await require_user_permission(
        namespace=IDEAS_NAMESPACE,
        kind=_KIND,
        resource_id=_resource_id(parent_id),
        relation="editor",
        user_id=user_id,
    )

    collection = _collection()
    rank = await _next_rank(user_id, parent_id)
    node_id = uuid4().hex
    doc = {
        "_id": node_id,
        "parent_id": parent_id,
        "title": title,
        "note": note,
        "rank": rank,
        "owner_id": user_id,
    }
    await collection.insert_one(doc)
    return _doc_to_model(doc)


async def _fetch_node_for_user(user_id: str, node_id: str) -> dict:
    collection = _collection()
    doc = await collection.find_one({"_id": node_id, "owner_id": user_id})
    if not doc:
        raise IdeaNotFoundError(f"Node {node_id} not found for user {user_id}")
    return doc


async def move_node_for_user(
    user_id: str,
    node_id: str,
    new_parent_id: Optional[str],
) -> IdeaNode:
    """Move a node to a new parent and append it to the end."""

    node = await _fetch_node_for_user(user_id, node_id)
    old_parent_id = node.get("parent_id")

    if old_parent_id is None or new_parent_id is None:
        await _ensure_root_permissions(user_id)

    await require_user_permission(
        namespace=IDEAS_NAMESPACE,
        kind=_KIND,
        resource_id=_resource_id(old_parent_id),
        relation="editor",
        user_id=user_id,
    )
    await require_user_permission(
        namespace=IDEAS_NAMESPACE,
        kind=_KIND,
        resource_id=_resource_id(new_parent_id),
        relation="editor",
        user_id=user_id,
    )

    rank = await _next_rank(user_id, new_parent_id)
    collection = _collection()
    await collection.update_one(
        {"_id": node_id},
        {"$set": {"parent_id": new_parent_id, "rank": rank}},
    )
    node.update({"parent_id": new_parent_id, "rank": rank})
    return _doc_to_model(node)


async def reorder_node_for_user(
    user_id: str,
    node_id: str,
    direction: Optional[str] = None,
    target_rank: Optional[float] = None,
) -> IdeaNode:
    """Reorder a node within its sibling set (MVP supports up/down)."""

    _ = target_rank  # reserved for future precise rank updates
    node = await _fetch_node_for_user(user_id, node_id)
    parent_id = node.get("parent_id")

    if parent_id is None:
        await _ensure_root_permissions(user_id)

    await require_user_permission(
        namespace=IDEAS_NAMESPACE,
        kind=_KIND,
        resource_id=_resource_id(parent_id),
        relation="editor",
        user_id=user_id,
    )

    if direction not in {"up", "down"}:
        return _doc_to_model(node)

    collection = _collection()
    cursor = (
        collection.find({"parent_id": parent_id, "owner_id": user_id})
        .sort("rank", 1)
    )
    siblings = [doc async for doc in cursor]
    index = next((idx for idx, doc in enumerate(siblings) if doc["_id"] == node_id), None)
    if index is None:
        raise IdeaNotFoundError(f"Node {node_id} not found among siblings")

    if direction == "up" and index == 0:
        return _doc_to_model(node)
    if direction == "down" and index == len(siblings) - 1:
        return _doc_to_model(node)

    swap_index = index - 1 if direction == "up" else index + 1
    target_node = siblings[swap_index]

    current_rank = siblings[index].get("rank", float(index))
    swap_rank = target_node.get("rank", float(swap_index))

    await collection.update_one({"_id": node_id}, {"$set": {"rank": swap_rank}})
    await collection.update_one({"_id": target_node["_id"]}, {"$set": {"rank": current_rank}})

    node.update({"rank": swap_rank})
    return _doc_to_model(node)
