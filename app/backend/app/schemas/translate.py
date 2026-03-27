from typing import Literal

from pydantic import BaseModel, Field


TranslateDirection = Literal["en2zh", "zh2en"]


class TranslateRequest(BaseModel):
    text: str = Field(min_length=1, description="Source text to translate")
    direction: TranslateDirection = "en2zh"


class TranslateResponse(BaseModel):
    direction: TranslateDirection
    source_text: str
    translated_text: str
    model: str
    provider_url: str
    raw_response: dict
