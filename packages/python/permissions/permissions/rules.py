from __future__ import annotations

from .keto_client import keto_check
from .subjects import user_subject


def build_object_id(namespace: str, kind: str, resource_id: str) -> str:
    """
    Return a canonical Keto object id, e.g. `list:123`.
    The namespace parameter is accepted for ergonomic parity with other helpers.
    """

    return f"{kind}:{resource_id}"


async def can_view(
    namespace: str,
    kind: str,
    resource_id: str,
    user_id: str,
) -> bool:
    """Check whether the given user can view the resource."""

    return await keto_check(
        namespace=namespace,
        object=build_object_id(namespace, kind, resource_id),
        relation="viewer",
        subject=user_subject(user_id),
    )


async def can_edit(
    namespace: str,
    kind: str,
    resource_id: str,
    user_id: str,
) -> bool:
    """Check whether the given user can edit the resource."""

    return await keto_check(
        namespace=namespace,
        object=build_object_id(namespace, kind, resource_id),
        relation="editor",
        subject=user_subject(user_id),
    )
