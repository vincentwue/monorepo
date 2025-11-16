"""Settings for the core server FastAPI application."""

from __future__ import annotations

import os
from typing import List

from dotenv import find_dotenv, load_dotenv
from pydantic import BaseModel, Field

# Search for the nearest .env so running from subdirectories still loads root config.
load_dotenv(find_dotenv(usecwd=True))


def _default_cors_origins() -> List[str]:
    """Build the default list of CORS origins."""

    raw = os.getenv("CORE_CORS_ALLOW_ORIGINS")
    if raw:
        return [origin.strip() for origin in raw.split(",") if origin.strip()]
    derived = []
    for key in ("APP_BASE_URL", "AUTH_UI_BASE_URL"):
        value = os.getenv(key)
        if value:
            derived.append(value.strip())
    return derived


class CoreSettings(BaseModel):
    """API metadata for the FastAPI app."""

    api_title: str = "Monorepo Core API"
    api_version: str = "0.1.0"
    cors_allow_origins: List[str] = Field(default_factory=_default_cors_origins)


settings = CoreSettings()
