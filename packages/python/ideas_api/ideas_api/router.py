"""FastAPI router exposing Ideas operations."""

from fastapi import APIRouter, Body, Depends, Query

from ideas_repo import (
    IdeaNode,
    create_child_for_user,
    list_children_for_user,
    move_node_for_user,
    reorder_node_for_user,
)

from .kratos_client import get_current_identity

router = APIRouter(prefix="/ideas", tags=["ideas"])


@router.get("/children", response_model=list[IdeaNode])
async def get_children(
    parent_id: str | None = Query(default=None),
    identity: dict = Depends(get_current_identity),
):
    """Return child nodes for the parent visible to the requesting identity."""

    user_id: str = identity["id"]
    return await list_children_for_user(user_id=user_id, parent_id=parent_id)


@router.post("/children", response_model=IdeaNode)
async def create_child(
    parent_id: str | None = Query(default=None),
    payload: dict = Body(...),
    identity: dict = Depends(get_current_identity),
):
    """Create a new child node below the provided parent."""

    user_id: str = identity["id"]
    title: str = payload["title"]
    note: str | None = payload.get("note")
    return await create_child_for_user(
        user_id=user_id,
        parent_id=parent_id,
        title=title,
        note=note,
    )


@router.post("/nodes/{node_id}/move", response_model=IdeaNode)
async def move_node(
    node_id: str,
    payload: dict = Body(...),
    identity: dict = Depends(get_current_identity),
):
    """Move an idea node to a new parent."""

    user_id: str = identity["id"]
    new_parent_id: str | None = payload.get("new_parent_id")
    return await move_node_for_user(
        user_id=user_id,
        node_id=node_id,
        new_parent_id=new_parent_id,
    )


@router.post("/nodes/{node_id}/reorder", response_model=IdeaNode)
async def reorder_node(
    node_id: str,
    payload: dict = Body(...),
    identity: dict = Depends(get_current_identity),
):
    """Reorder an idea node among its siblings."""

    user_id: str = identity["id"]
    direction: str | None = payload.get("direction")
    target_rank = payload.get("target_rank")
    return await reorder_node_for_user(
        user_id=user_id,
        node_id=node_id,
        direction=direction,
        target_rank=target_rank,
    )
