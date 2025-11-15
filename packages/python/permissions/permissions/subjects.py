from __future__ import annotations

from typing import Any, Mapping

USER_SUBJECT_PREFIX = "user"


def user_subject(user_id: str) -> str:
    """Return the canonical Keto subject string for a user id."""
    return f"{USER_SUBJECT_PREFIX}:{user_id}"


def subject_from_identity(identity: Mapping[str, Any]) -> str:
    """
    Convert a Kratos identity payload to the canonical Keto subject string.

    Raises:
        ValueError: if the identity lacks an 'id' property.
    """

    identity_id = identity.get("id")
    if not identity_id:
        raise ValueError("identity payload missing 'id'")
    return user_subject(str(identity_id))
