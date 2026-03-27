from fastapi import APIRouter

from app.core.settings import get_settings
from app.schemas.common import HealthResponse


router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        app=settings.app_name,
        environment=settings.app_env,
    )
