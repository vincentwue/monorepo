from __future__ import annotations

"""FastAPI router exposing Ideas operations."""

from fastapi import APIRouter, Body, Depends, Query, Response

from ideas_repo import (
    IdeaNode,
    create_child_for_user,
    list_children_for_user,
    list_tree_for_user,
    move_node_for_user,
    reorder_node_for_user,
    delete_node_for_user,
    update_node_for_user,
)

from .kratos_client import get_identity
from .workspace import extract_workspace_id

router = APIRouter(prefix="/ideas", tags=["ideas"])


@router.get("/children", response_model=list[IdeaNode])
async def get_children(
    parent_id: str | None = Query(default=None),
    identity: dict = Depends(get_identity),
):
    """Return child nodes for the parent visible to the requesting identity."""

    user_id: str = identity["id"]
    workspace_id = extract_workspace_id(identity)
    return await list_children_for_user(
        workspace_id=workspace_id,
        user_id=user_id,
        parent_id=parent_id,
    )


@router.get("/tree", response_model=list[IdeaNode])
async def get_tree(identity: dict = Depends(get_identity)):
    """Return the full idea tree visible to the requesting identity."""

    user_id: str = identity["id"]
    workspace_id = extract_workspace_id(identity)
    return await list_tree_for_user(
        workspace_id=workspace_id,
        user_id=user_id,
    )


@router.post("/children", response_model=IdeaNode)
async def create_child(
    parent_id: str | None = Query(default=None),
    after_id: str | None = Query(default=None),
    payload: dict = Body(...),
    identity: dict = Depends(get_identity),
):
    """Create a new child node below the provided parent."""

    user_id: str = identity["id"]
    workspace_id = extract_workspace_id(identity)
    title: str = payload["title"]
    note: str | None = payload.get("note")
    return await create_child_for_user(
        workspace_id=workspace_id,
        user_id=user_id,
        parent_id=parent_id,
        title=title,
        note=note,
        after_id=after_id,
    )


@router.post("/nodes/{node_id}/move", response_model=IdeaNode)
async def move_node(
    node_id: str,
    payload: dict = Body(...),
    identity: dict = Depends(get_identity),
):
    """Move an idea node to a new parent."""

    user_id: str = identity["id"]
    workspace_id = extract_workspace_id(identity)
    new_parent_id: str | None = payload.get("new_parent_id")
    return await move_node_for_user(
        workspace_id=workspace_id,
        user_id=user_id,
        node_id=node_id,
        new_parent_id=new_parent_id,
    )


@router.post("/nodes/{node_id}/reorder", response_model=IdeaNode)
async def reorder_node(
    node_id: str,
    payload: dict = Body(...),
    identity: dict = Depends(get_identity),
):
    """Reorder an idea node among its siblings."""

    user_id: str = identity["id"]
    workspace_id = extract_workspace_id(identity)
    direction: str | None = payload.get("direction")
    target_index = payload.get("target_index")
    return await reorder_node_for_user(
        workspace_id=workspace_id,
        user_id=user_id,
        node_id=node_id,
        direction=direction,
        target_rank=None,
        target_index=int(target_index) if isinstance(target_index, int) else None,
    )


@router.delete("/nodes/{node_id}", status_code=204)
async def delete_node(
    node_id: str,
    identity: dict = Depends(get_identity),
) -> Response:
    """Delete an idea node and its subtree."""

    user_id: str = identity["id"]
    workspace_id = extract_workspace_id(identity)
    await delete_node_for_user(
        workspace_id=workspace_id,
        user_id=user_id,
        node_id=node_id,
    )
    return Response(status_code=204)


@router.patch("/nodes/{node_id}", response_model=IdeaNode)
async def update_node(
    node_id: str,
    payload: dict = Body(...),
    identity: dict = Depends(get_identity),
):
    """Update a node's title or note."""

    user_id: str = identity["id"]
    workspace_id = extract_workspace_id(identity)
    title = payload.get("title")
    note = payload.get("note")
    return await update_node_for_user(
        workspace_id=workspace_id,
        user_id=user_id,
        node_id=node_id,
        title=title,
        note=note,
    )
