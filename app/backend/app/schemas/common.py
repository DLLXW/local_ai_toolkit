from datetime import datetime, timezone

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class HealthResponse(BaseModel):
    status: str = "ok"
    app: str
    environment: str
    timestamp: datetime = Field(default_factory=utc_now)


class ErrorResponse(BaseModel):
    detail: str
