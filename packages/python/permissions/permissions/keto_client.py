from __future__ import annotations

from typing import Optional

import httpx

from .config import settings


def _timeout_value(timeout: Optional[float]) -> float:
    return timeout if timeout is not None else settings.timeout_seconds


async def keto_check(
    namespace: str,
    object: str,
    relation: str,
    subject: str,
    *,
    timeout: Optional[float] = None,
) -> bool:
    """
    Call Keto's relation-tuple check endpoint and return True if allowed.
    """

    payload = {
        "namespace": namespace,
        "object": object,
        "relation": relation,
        "subject_id": subject,
    }
    url = f"{settings.keto_read_url.rstrip('/')}/relation-tuples/check"
    async with httpx.AsyncClient(timeout=_timeout_value(timeout)) as client:
        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            # Keto returns 403 when checks fail; map that to allowed=False.
            if exc.response is not None and exc.response.status_code == 403:
                return False
            raise
        data = response.json()
    return bool(data.get("allowed"))


async def keto_write(
    namespace: str,
    object: str,
    relation: str,
    subject: str,
    *,
    timeout: Optional[float] = None,
) -> None:
    """
    Write (upsert) a relation tuple to Keto's write API.
    """

    payload = {
        "namespace": namespace,
        "object": object,
        "relation": relation,
        "subject_id": subject,
    }
    url = f"{settings.keto_write_url.rstrip('/')}/admin/relation-tuples"
    async with httpx.AsyncClient(timeout=_timeout_value(timeout)) as client:
        response = await client.put(url, json=payload)
        response.raise_for_status()
