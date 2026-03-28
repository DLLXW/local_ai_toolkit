from pydantic import BaseModel, Field

from app.schemas.translate import TranslateDirection


class WebpageTranslateRequest(BaseModel):
    url: str = Field(min_length=1)
    direction: TranslateDirection = "en2zh"


class WebpageTranslateResponse(BaseModel):
    url: str
    title: str
    source_markdown: str
    translated_markdown: str
    source_excerpt: str
    ssl_fallback_used: bool = False
    fetch_seconds: float | None = None
    translation_seconds: float | None = None
    total_seconds: float | None = None
