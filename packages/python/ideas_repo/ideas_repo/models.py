"""Pydantic models describing Idea nodes."""

from typing import Optional

from pydantic import BaseModel, Field


class IdeaNode(BaseModel):
    """Representation of an idea entry stored in MongoDB."""

    id: str
    parent_id: Optional[str] = None
    title: str
    note: Optional[str] = None
    rank: float = Field(default=0)
    owner_id: str


class IdeaCreate(BaseModel):
    """Payload for creating a new idea child node."""

    parent_id: Optional[str] = None
    title: str
    note: Optional[str] = None


class IdeaUpdate(BaseModel):
    """Payload for updating title/note of an idea node."""

    title: Optional[str] = None
    note: Optional[str] = None
