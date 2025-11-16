from __future__ import annotations

from typing import Any

DEFAULT_WORKSPACE_ID = "home_workspace"
HOME_WORKSPACE_SUFFIX = "ideas_home"


def _normalize_workspace_id(value: Any) -> str | None:
    if isinstance(value, str):
        trimmed = value.strip()
        if trimmed:
            return trimmed
    return None


def _workspace_id_from_traits(identity: dict[str, Any]) -> str | None:
    traits = identity.get("traits")
    if isinstance(traits, dict):
        return _normalize_workspace_id(traits.get("workspace_id"))
    return None


def _default_workspace_for_user(identity: dict[str, Any]) -> str | None:
    user_id = _normalize_workspace_id(identity.get("id"))
    if not user_id:
        return None
    return f"{user_id}-{HOME_WORKSPACE_SUFFIX}"


def extract_workspace_id(identity: dict[str, Any]) -> str:
    """
    Return the workspace id for the given identity.

    Prefer the workspace_id trait when present; otherwise fall back to a
    deterministic "home" workspace derived from the identity id so every user
    has a private ideas workspace.
    """

    workspace_id = _workspace_id_from_traits(identity)
    if workspace_id:
        return workspace_id

    fallback = _default_workspace_for_user(identity)
    if fallback:
        return fallback

    return DEFAULT_WORKSPACE_ID
