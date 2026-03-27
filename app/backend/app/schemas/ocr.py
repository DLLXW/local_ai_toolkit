from pydantic import BaseModel


class OCRResponse(BaseModel):
    markdown: str
    raw_text: str
    model: str
    provider_url: str
    raw_response: dict
