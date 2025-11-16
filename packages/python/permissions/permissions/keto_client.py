from __future__ import annotations

import time
from typing import Optional, Set, Tuple

import httpx
from loguru import logger

from .config import settings

# ---------------------------------------------------------------------------
# Client setup
# ---------------------------------------------------------------------------

# Shared clients so we reuse TCP connections instead of re-creating them
# on every keto_check / keto_write call.
_read_client: httpx.AsyncClient | None = None
_write_client: httpx.AsyncClient | None = None


def _timeout_value(timeout: Optional[float]) -> float:
    return timeout if timeout is not None else settings.timeout_seconds


def _get_read_client() -> httpx.AsyncClient:
    global _read_client
    if _read_client is None:
        _read_client = httpx.AsyncClient()
    return _read_client


def _get_write_client() -> httpx.AsyncClient:
    global _write_client
    if _write_client is None:
        _write_client = httpx.AsyncClient()
    return _write_client


# ---------------------------------------------------------------------------
# Write de-duplication cache
# ---------------------------------------------------------------------------

# Prevent spamming Keto with the same tuple over and over again.
# This is process-local and intentionally simple; if you ever need to clear it
# (e.g. in tests), just reset _written_cache = set().
_written_cache: Set[Tuple[str, str, str, str]] = set()


def _write_cache_key(
    namespace: str,
    object: str,
    relation: str,
    subject: str,
) -> tuple[str, str, str, str]:
    return (namespace, object, relation, subject)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


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

    client = _get_read_client()
    start = time.perf_counter()
    try:
        response = await client.post(
            url,
            json=payload,
            timeout=_timeout_value(timeout),
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        duration = (time.perf_counter() - start) * 1000
        logger.warning(
            "Keto check {namespace} {object}/{relation} for {subject} failed after {duration:.2f} ms: {error}",
            namespace=namespace,
            object=object,
            relation=relation,
            subject=subject,
            duration=duration,
            error=exc,
        )
        # Keto returns 403 when checks fail; map that to allowed=False.
        if exc.response is not None and exc.response.status_code == 403:
            return False
        # Any other status is an actual error.
        raise

    data = response.json()
    duration = (time.perf_counter() - start) * 1000
    allowed = bool(data.get("allowed"))
    logger.debug(
        "Keto check {namespace} {object}/{relation} for {subject} -> {result} in {duration:.2f} ms",
        namespace=namespace,
        object=object,
        relation=relation,
        subject=subject,
        result=allowed,
        duration=duration,
    )
    return allowed


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

    This implementation is idempotent on the process level: if the same
    (namespace, object, relation, subject) tuple was already written during
    this process lifetime, the call will be skipped.
    """

    key = _write_cache_key(namespace, object, relation, subject)
    if key in _written_cache:
        # Already written in this process; skip the HTTP call entirely.
        logger.debug(
            "Keto write {namespace} {object}/{relation} <- {subject} skipped (already written in-process)",
            namespace=namespace,
            object=object,
            relation=relation,
            subject=subject,
        )
        return

    payload = {
        "namespace": namespace,
        "object": object,
        "relation": relation,
        "subject_id": subject,
    }
    url = f"{settings.keto_write_url.rstrip('/')}/admin/relation-tuples"

    client = _get_write_client()
    start = time.perf_counter()
    response = await client.put(
        url,
        json=payload,
        timeout=_timeout_value(timeout),
    )
    response.raise_for_status()
    duration = (time.perf_counter() - start) * 1000

    _written_cache.add(key)

    logger.debug(
        "Keto write {namespace} {object}/{relation} <- {subject} completed in {duration:.2f} ms",
        namespace=namespace,
        object=object,
        relation=relation,
        subject=subject,
        duration=duration,
    )
