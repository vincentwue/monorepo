"""FastAPI application composing the ideas API router."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ideas_api import router as ideas_router, settings_router as idea_settings_router
import loguru
from permissions import permissions_router

from .config import settings

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
    
loguru.logger.info("CORS middleware added"+str(settings.cors_allow_origins))


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
