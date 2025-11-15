import os

from pydantic import BaseModel, Field


class PermissionsSettings(BaseModel):
    """Runtime configuration for interacting with Ory Keto."""

    keto_read_url: str = Field(
        default_factory=lambda: os.getenv("KETO_READ_URL", "http://keto:4466")
    )
    keto_write_url: str = Field(
        default_factory=lambda: os.getenv("KETO_WRITE_URL", "http://keto:4467")
    )
    timeout_seconds: float = Field(
        default_factory=lambda: float(os.getenv("PERMISSIONS_TIMEOUT_SECONDS", "2.0"))
    )


settings = PermissionsSettings()
