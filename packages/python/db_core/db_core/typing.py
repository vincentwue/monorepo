"""Lightweight typing helpers shared by Mongo-backed repositories."""

from typing import Any, Mapping, Protocol


class DocumentLike(Protocol):
    """Minimal protocol describing mapping-style MongoDB documents."""

    def __getitem__(self, key: str) -> Any:  # pragma: no cover - structural typing only
        ...


MongoDocument = Mapping[str, Any]
