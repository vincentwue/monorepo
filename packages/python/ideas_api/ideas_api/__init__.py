"""Expose the Ideas FastAPI routers."""

from .router import router
from .settings_router import router as settings_router

__all__ = ["router", "settings_router"]
