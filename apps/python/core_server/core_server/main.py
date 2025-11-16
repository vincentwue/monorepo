"""FastAPI application composing the ideas API router."""

from __future__ import annotations

import os
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from dotenv import find_dotenv, load_dotenv

from ._paths import ensure_local_packages_importable

ensure_local_packages_importable()
load_dotenv(find_dotenv(usecwd=True))


def _configure_logging() -> None:
    level = os.getenv("LOG_LEVEL") or os.getenv("LOGURU_LEVEL") or "INFO"
    logger.remove()
    logger.add(sys.stderr, level=level.upper())
    logger.info("Logger configured at {level} level", level=level.upper())


from .config import settings
from ideas_api import router as ideas_router, settings_router as idea_settings_router
from permissions import permissions_router


_configure_logging()

app = FastAPI(title=settings.api_title, version=settings.api_version)

# Allow the front-end origins (with credentials) to talk to this API.
if settings.cors_allow_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
logger.info("CORS middleware added {origins}", origins=settings.cors_allow_origins)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    """Simple liveness endpoint for load balancers and probes."""

    return {"status": "ok"}


app.include_router(permissions_router)
app.include_router(ideas_router)
app.include_router(idea_settings_router)

"""Run with:

    uvicorn core_server.main:app --host 0.0.0.0 --port 8000 --reload
"""
