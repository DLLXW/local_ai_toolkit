from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.system import router as system_router
from app.api.tasks import router as tasks_router
from app.api.tools import router as tools_router
from app.core.settings import get_settings


settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(system_router, prefix="/api")
app.include_router(tasks_router, prefix="/api")
app.include_router(tools_router, prefix="/api")
app.mount("/static/outputs", StaticFiles(directory=settings.outputs_dir), name="outputs")


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "name": settings.app_name,
        "docs": "/docs",
        "health": "/api/health",
    }
