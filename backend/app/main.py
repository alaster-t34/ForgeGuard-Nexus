from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, ORJSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.bootstrap import seed_store
from app.config import get_settings
from app.runtime import runtime

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    seed_store(runtime.store)
    yield


app = FastAPI(
    title="ForgeGuard Nexus API",
    version=settings.app_version,
    description="Human-centric, resilient and sustainable Industrial 5.0 edge maintenance agent platform",
    default_response_class=ORJSONResponse,
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)
app.include_router(router, prefix=settings.api_prefix)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIR = PROJECT_ROOT / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/ui", StaticFiles(directory=FRONTEND_DIR), name="ui")


@app.get("/", include_in_schema=False)
async def root():
    index = FRONTEND_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    return {
        "name": "ForgeGuard Nexus",
        "message": "Industrial intelligence with evidence, approval, and verification.",
        "docs": "/docs",
    }
