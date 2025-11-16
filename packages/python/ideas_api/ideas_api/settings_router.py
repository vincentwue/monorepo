"""FastAPI router for persisting UI settings."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from settings_repo import IdeaTreeUiState
from settings_repo.service import get_idea_tree_state, update_idea_tree_state

from .kratos_client import get_identity
from .workspace import extract_workspace_id

router = APIRouter(prefix="/settings", tags=["settings"])


class IdeaTreeSettingsPayload(BaseModel):
    expanded_ids: list[str] = Field(default_factory=list)
    selected_id: str | None = None


@router.get("/idea-tree", response_model=IdeaTreeUiState)
async def read_idea_tree_settings(identity: dict = Depends(get_identity)):
    user_id: str = identity["id"]
    workspace_id = extract_workspace_id(identity)
    return await get_idea_tree_state(workspace_id=workspace_id, user_id=user_id)


@router.put("/idea-tree", response_model=IdeaTreeUiState)
async def update_idea_tree_settings(
    payload: IdeaTreeSettingsPayload,
    identity: dict = Depends(get_identity),
):
    user_id: str = identity["id"]
    workspace_id = extract_workspace_id(identity)
    return await update_idea_tree_state(
        workspace_id=workspace_id,
        user_id=user_id,
        expanded_ids=payload.expanded_ids,
        selected_id=payload.selected_id,
    )
