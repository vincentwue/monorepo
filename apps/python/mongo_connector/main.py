from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.router import router

app = FastAPI(title="Mongo Connector")

# ✅ Proper CORS config
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or ["http://localhost:5173"] for stricter config
    allow_origin_regex="http://localhost:5173",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8010)
