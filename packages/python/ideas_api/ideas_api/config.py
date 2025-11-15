"""Configuration for the ideas API package."""

import os

from pydantic import BaseModel, Field


class IdeasApiSettings(BaseModel):
    """Settings for interacting with identity providers."""

    kratos_public_url: str = Field(
        default_factory=lambda: os.getenv("KRATOS_PUBLIC_URL", "http://kratos:4433")
    )


settings = IdeasApiSettings()
