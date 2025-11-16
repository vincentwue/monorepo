import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.router import router

app = FastAPI(title="Mongo Connector")

raw_origins = os.getenv("MONGO_CONNECTOR_CORS_ALLOW_ORIGINS", "*")
allow_origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()] or ["*"]
origin_regex = os.getenv("MONGO_CONNECTOR_ALLOW_ORIGIN_REGEX")

# ?o. Proper CORS config
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_origin_regex=origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("MONGO_CONNECTOR_PORT", "8010"))
    uvicorn.run(app, host="0.0.0.0", port=port)
