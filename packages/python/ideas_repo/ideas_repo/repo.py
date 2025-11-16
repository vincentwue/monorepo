"""Async persistence layer for ideas along with permission enforcement."""

from __future__ import annotations

import asyncio
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
ROOT_RESOURCE_KEY = "root"

# Optional: visible name for the “root idea” node.
DEFAULT_ROOT_TITLE = "My ideas"

_ROOT_PERMISSION_CACHE: set[str] = set()
_ROOT_PERMISSION_LOCK = asyncio.Lock()


def _workspace_root_object_id(workspace_id: str) -> str:
    """Fully-qualified Keto object id for the workspace's root ideas space."""
    return build_object_id(IDEAS_NAMESPACE, _KIND, f"{workspace_id}:{ROOT_RESOURCE_KEY}")


def _resource_id(workspace_id: str, node_id: Optional[str]) -> str:
    """Logical resource id part used with build_object_id / Keto checks."""
    if not node_id:
        return f"{workspace_id}:{ROOT_RESOURCE_KEY}"
    return f"{workspace_id}:{node_id}"


def _collection():
    return get_db()[COLLECTION_NAME]


def _doc_to_model(doc: dict) -> IdeaNode:
    return IdeaNode(
        id=str(doc.get("_id") or doc["id"]),
        parent_id=doc.get("parent_id"),
        title=doc["title"],
        note=doc.get("note"),
        rank=float(doc.get("rank", 0)),
        owner_id=doc.get("workspace_id") or doc.get("owner_id"),
    )


async def _ensure_root_permissions(user_id: str, workspace_id: str) -> None:
    """
    Ensure the requesting user has default viewer/editor permissions
    on their personal root node so first-time access succeeds.

    This is the *only* object we use for permission checks in the MVP.
    """

    cache_key = f"{user_id}:{workspace_id}"
    if cache_key in _ROOT_PERMISSION_CACHE:
        return

    async with _ROOT_PERMISSION_LOCK:
        if cache_key in _ROOT_PERMISSION_CACHE:
            return

        subject = user_subject(user_id)
        root_object = _workspace_root_object_id(workspace_id)
        for relation in ("viewer", "editor"):
            await keto_write(
                namespace=IDEAS_NAMESPACE,
                object=root_object,
                relation=relation,
                subject=subject,
            )

        _ROOT_PERMISSION_CACHE.add(cache_key)


async def _get_or_create_root_node(workspace_id: str, user_id: str) -> dict:
    """
    Ensure there is exactly one persisted 'root idea' node per workspace.

    - It has `parent_id = None`
    - It is marked with `is_root: True`
    - We grant viewer/editor permissions to the user that caused it to exist.
    """

    collection = _collection()

    # Look for an existing root node for this workspace.
    existing = await collection.find_one(
        {"workspace_id": workspace_id, "parent_id": None, "is_root": True}
    )
    if existing:
        return existing

    # Create a new root idea node.
    node_id = uuid4().hex
    doc = {
        "_id": node_id,
        "parent_id": None,
        "title": DEFAULT_ROOT_TITLE,
        "note": None,
        "rank": 0.0,
        "workspace_id": workspace_id,
        "is_root": True,
    }
    await collection.insert_one(doc)

    # Grant permissions on this node to the current user.
    await _grant_node_permissions(workspace_id, user_id, node_id)
    return doc


async def list_children_for_user(
    workspace_id: str,
    user_id: str,
    parent_id: Optional[str],
) -> List[IdeaNode]:
    """List child nodes visible to the user under the provided parent."""

    # Ensure root entitlements exist and enforce "viewer" on the workspace root.
    await _ensure_root_permissions(user_id, workspace_id)
    await require_user_permission(
        namespace=IDEAS_NAMESPACE,
        kind=_KIND,
        resource_id=_resource_id(workspace_id, None),  # workspace root
        relation="viewer",
        user_id=user_id,
    )

    # Make sure the root idea node exists for this workspace.
    await _get_or_create_root_node(workspace_id, user_id)

    collection = _collection()
    cursor = (
        collection.find({"parent_id": parent_id, "workspace_id": workspace_id})
        .sort("rank", 1)
    )

    docs = [doc async for doc in cursor]
    return [_doc_to_model(doc) for doc in docs]


async def list_tree_for_user(workspace_id: str, user_id: str) -> List[IdeaNode]:
    """Return all idea nodes visible to the user for the workspace."""

    await _ensure_root_permissions(user_id, workspace_id)
    await require_user_permission(
        namespace=IDEAS_NAMESPACE,
        kind=_KIND,
        resource_id=_resource_id(workspace_id, None),  # workspace root
        relation="viewer",
        user_id=user_id,
    )

    # Ensure the root idea exists before returning the tree.
    await _get_or_create_root_node(workspace_id, user_id)

    collection = _collection()
    cursor = (
        collection.find({"workspace_id": workspace_id})
        .sort("parent_id", 1)
        .sort("rank", 1)
    )
    docs = [doc async for doc in cursor]
    return [_doc_to_model(doc) for doc in docs]


async def _next_rank(workspace_id: str, parent_id: Optional[str]) -> float:
    collection = _collection()
    cursor = (
        collection.find({"parent_id": parent_id, "workspace_id": workspace_id})
        .sort("rank", -1)
        .limit(1)
    )
    docs = await cursor.to_list(length=1)
    if docs:
        return float(docs[0].get("rank", 0)) + 1
    return 0.0


async def create_child_for_user(
    workspace_id: str,
    user_id: str,
    parent_id: Optional[str],
    title: str,
    note: Optional[str] = None,
) -> IdeaNode:
    """
    Create a child node and append it to the end of the sibling list.

    IMPORTANT: Users cannot create additional "root" ideas.
    - If parent_id is None, we automatically attach the new idea to
      the workspace's root idea node.
    """

    # Root permissions + "editor" on workspace root is enough to create anywhere.
    await _ensure_root_permissions(user_id, workspace_id)
    await require_user_permission(
        namespace=IDEAS_NAMESPACE,
        kind=_KIND,
        resource_id=_resource_id(workspace_id, None),  # workspace root
        relation="editor",
        user_id=user_id,
    )

    # If no parent was specified, attach to the (single) root idea node.
    if parent_id is None:
        root_doc = await _get_or_create_root_node(workspace_id, user_id)
        parent_id = str(root_doc["_id"])

    collection = _collection()
    rank = await _next_rank(workspace_id, parent_id)
    node_id = uuid4().hex
    doc = {
        "_id": node_id,
        "parent_id": parent_id,
        "title": title,
        "note": note,
        "rank": rank,
        "workspace_id": workspace_id,
        # NOTE: this is a normal idea, not a root:
        "is_root": False,
    }
    await collection.insert_one(doc)

    # We still grant per-node tuples for future finer-grained models.
    await _grant_node_permissions(workspace_id, user_id, node_id)
    return _doc_to_model(doc)


async def _grant_node_permissions(workspace_id: str, user_id: str, node_id: str) -> None:
    """Grant viewer/editor on a specific node (reserved for future fine-grain ACL)."""
    object_id = build_object_id(IDEAS_NAMESPACE, _KIND, _resource_id(workspace_id, node_id))
    subject = user_subject(user_id)
    for relation in ("viewer", "editor"):
        await keto_write(
            namespace=IDEAS_NAMESPACE,
            object=object_id,
            relation=relation,
            subject=subject,
        )


async def _fetch_node_for_user(workspace_id: str, user_id: str, node_id: str) -> dict:
    collection = _collection()
    doc = await collection.find_one({"_id": node_id, "workspace_id": workspace_id})
    if not doc:
        raise IdeaNotFoundError(f"Node {node_id} not found for user {user_id}")
    return doc


async def move_node_for_user(
    workspace_id: str,
    user_id: str,
    node_id: str,
    new_parent_id: Optional[str],
) -> IdeaNode:
    """Move a node to a new parent and append it to the end."""

    node = await _fetch_node_for_user(workspace_id, user_id, node_id)

    # Do not allow moving the root idea itself.
    if node.get("is_root") and node.get("parent_id") is None:
        # Simply return unchanged; root is immovable.
        return _doc_to_model(node)

    # Root permissions + "editor" on workspace root control moving anywhere.
    await _ensure_root_permissions(user_id, workspace_id)
    await require_user_permission(
        namespace=IDEAS_NAMESPACE,
        kind=_KIND,
        resource_id=_resource_id(workspace_id, None),  # workspace root
        relation="editor",
        user_id=user_id,
    )

    # If someone tries to move under "no parent", normalize to root node.
    if new_parent_id is None:
        root_doc = await _get_or_create_root_node(workspace_id, user_id)
        new_parent_id = str(root_doc["_id"])

    rank = await _next_rank(workspace_id, new_parent_id)
    collection = _collection()
    await collection.update_one(
        {"_id": node_id, "workspace_id": workspace_id},
        {"$set": {"parent_id": new_parent_id, "rank": rank}},
    )
    node.update({"parent_id": new_parent_id, "rank": rank})
    return _doc_to_model(node)


async def reorder_node_for_user(
    workspace_id: str,
    user_id: str,
    node_id: str,
    direction: Optional[str] = None,
    target_rank: Optional[float] = None,
) -> IdeaNode:
    """Reorder a node within its sibling set (MVP supports up/down)."""

    _ = target_rank  # reserved for future precise rank updates
    node = await _fetch_node_for_user(workspace_id, user_id, node_id)

    # Root idea is not reorderable relative to anything (it has no siblings).
    if node.get("is_root") and node.get("parent_id") is None:
        return _doc_to_model(node)

    parent_id = node.get("parent_id")

    # Root permissions + "editor" on workspace root control reordering anywhere.
    await _ensure_root_permissions(user_id, workspace_id)
    await require_user_permission(
        namespace=IDEAS_NAMESPACE,
        kind=_KIND,
        resource_id=_resource_id(workspace_id, None),  # workspace root
        relation="editor",
        user_id=user_id,
    )

    if direction not in {"up", "down"}:
        return _doc_to_model(node)

    collection = _collection()
    cursor = (
        collection.find({"parent_id": parent_id, "workspace_id": workspace_id})
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


async def delete_node_for_user(
    workspace_id: str,
    user_id: str,
    node_id: str,
) -> None:
    """
    Delete a node and its entire subtree.

    Constraints:
    - The "root idea" (parent_id is None and is_root is True) cannot be deleted.
    """

    # Make sure the node exists (and is in this workspace).
    node = await _fetch_node_for_user(workspace_id, user_id, node_id)

    # Do not allow deleting the root idea.
    if node.get("is_root") and node.get("parent_id") is None:
        # No-op. Caller sees 204 but root remains.
        return

    # Root permissions + "editor" on workspace root control deletion anywhere.
    await _ensure_root_permissions(user_id, workspace_id)
    await require_user_permission(
        namespace=IDEAS_NAMESPACE,
        kind=_KIND,
        resource_id=_resource_id(workspace_id, None),  # workspace root
        relation="editor",
        user_id=user_id,
    )

    collection = _collection()

    # Collect subtree ids starting at node_id
    to_visit = [node_id]
    all_ids = [node_id]

    while to_visit:
        current = to_visit.pop(0)
        cursor = collection.find({"parent_id": current, "workspace_id": workspace_id})
        children = [doc async for doc in cursor]
        child_ids = [str(doc["_id"]) for doc in children]
        if child_ids:
            all_ids.extend(child_ids)
            to_visit.extend(child_ids)

    # Hard-delete the node and all descendants.
    await collection.delete_many(
        {
            "_id": {"$in": all_ids},
            "workspace_id": workspace_id,
        }
    )

    # NOTE: We currently do not clean up per-node Keto tuples here.
    # For the MVP (root-based checks), this is acceptable. We can add
    # a keto_delete helper later if needed.
