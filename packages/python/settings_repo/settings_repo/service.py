from __future__ import annotations

from typing import Iterable, List, Optional

from .models import IdeaTreeUiState
from .repository import get_user_settings, upsert_idea_tree_state


def _dedupe(values: Iterable[str]) -> List[str]:
    seen: set[str] = set()
    result: List[str] = []
    for value in values:
        if not value:
            continue
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


async def get_idea_tree_state(workspace_id: str, user_id: str) -> IdeaTreeUiState:
    doc = await get_user_settings(workspace_id, user_id)
    return doc.idea_tree


async def update_idea_tree_state(
    workspace_id: str,
    user_id: str,
    expanded_ids: Iterable[str],
    selected_id: Optional[str],
) -> IdeaTreeUiState:
    state = IdeaTreeUiState(
        expanded_ids=_dedupe(expanded_ids),
        selected_id=selected_id or None,
    )
    doc = await upsert_idea_tree_state(workspace_id, user_id, state)
    return doc.idea_tree
