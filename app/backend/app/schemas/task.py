from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

TaskStatus = Literal["queued", "running", "done", "failed"]
TaskKind = Literal["ocr", "translate", "doc_translate"]


class TaskRecord(BaseModel):
    id: str
    kind: TaskKind
    status: TaskStatus
    title: str
    created_at: datetime
    updated_at: datetime
    input_filename: str | None = None
    doc_name: str | None = None
    progress: float = 0.0
    step: str = "queued"
    error: str | None = None
    result_path: str | None = None
    ocr_seconds: float | None = None
    translation_seconds: float | None = None
    total_seconds: float | None = None


class TaskListResponse(BaseModel):
    items: list[TaskRecord] = Field(default_factory=list)


class TaskDetailResponse(BaseModel):
    task: TaskRecord
