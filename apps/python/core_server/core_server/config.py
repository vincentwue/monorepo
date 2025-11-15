"""Settings for the core server FastAPI application."""

from __future__ import annotations

import os
from typing import List

from pydantic import BaseModel, Field


def _default_cors_origins() -> List[str]:
    """Build the default list of CORS origins."""

    raw = os.getenv("CORE_CORS_ALLOW_ORIGINS")
    if raw:
        return [origin.strip() for origin in raw.split(",") if origin.strip()]
    # Local dev defaults: SPA (5174) + auth UI (5173)
    return ["http://localhost:5174", "http://localhost:5173"]


class CoreSettings(BaseModel):
    """API metadata for the FastAPI app."""

    api_title: str = "Monorepo Core API"
    api_version: str = "0.1.0"
    cors_allow_origins: List[str] = Field(default_factory=_default_cors_origins)


settings = CoreSettings()
