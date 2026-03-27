from typing import Any

from pydantic import BaseModel, Field

from app.schemas.task import TaskRecord


class UploadResponse(BaseModel):
    task: TaskRecord


class DocumentSegment(BaseModel):
    kind: str
    source: str
    target: str


class DocumentResultResponse(BaseModel):
    doc_name: str
    asset_base_url: str | None = None
    english_markdown: str
    chinese_markdown: str
    bilingual_markdown: str
    segments: list[DocumentSegment] = Field(default_factory=list)
    ocr_json: list[Any] = Field(default_factory=list)


class DocumentViewResponse(BaseModel):
    doc_name: str
    mode: str
    content: str
