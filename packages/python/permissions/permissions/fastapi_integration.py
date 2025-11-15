from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from .keto_client import keto_check
from .rules import build_object_id
from .subjects import user_subject


class PermissionCheck(BaseModel):
    namespace: str
    object: str
    relation: str
    subject: str


async def require_permission(perm: PermissionCheck) -> None:
    """
    Execute a permission check and raise 403 if it fails.
    """

    allowed = await keto_check(**perm.model_dump())
    if not allowed:
        raise HTTPException(status_code=403, detail="Forbidden")


async def require_user_permission(
    *,
    namespace: str,
    kind: str,
    resource_id: str,
    relation: str,
    user_id: str,
) -> None:
    """
    Higher-level helper that builds the Keto object + subject automatically.

    Example usage with Kratos identities:

    ```python
    from fastapi import Depends
    from permissions.fastapi_integration import require_user_permission
    from permissions.subjects import subject_from_identity

    @app.get("/lists/{list_id}")
    async def get_list(list_id: str, identity = Depends(get_current_identity)):
        user_id = identity["id"]
        await require_user_permission(
            namespace="app:todos",
            kind="list",
            resource_id=list_id,
            relation="viewer",
            user_id=user_id,
        )
        return await db.get_list(list_id)
    ```
    """

    await require_permission(
        PermissionCheck(
            namespace=namespace,
            object=build_object_id(namespace, kind, resource_id),
            relation=relation,
            subject=user_subject(user_id),
        )
    )


router = APIRouter(prefix="/permissions", tags=["permissions"])


@router.get("/check")
async def check_permission_endpoint(
    namespace: str = Query(...),
    object: str = Query(...),
    relation: str = Query(...),
    subject: str = Query(...),
):
    allowed = await keto_check(namespace, object, relation, subject)
    return {"allowed": allowed}
