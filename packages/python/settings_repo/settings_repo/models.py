from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class IdeaTreeUiState(BaseModel):
    """
    UI state for the ideas tree.

    - expanded_ids: which idea nodes are expanded in the tree
    - selected_id: which idea node is currently selected / focused
    """

    expanded_ids: List[str] = Field(default_factory=list)
    selected_id: Optional[str] = None


class UserSettingsDocument(BaseModel):
    """
    Root settings document stored in the DB per user.

    For now we only store idea tree UI state, but this is expandable later
    (e.g. theme, language, feature flags, etc.).
    """

    user_id: str

    # UI state for the ideas tree
    idea_tree: IdeaTreeUiState = Field(default_factory=IdeaTreeUiState)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
