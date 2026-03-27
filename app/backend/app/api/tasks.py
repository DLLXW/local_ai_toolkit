from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.core.settings import Settings, get_settings
from app.schemas.document import (
    DocumentResultResponse,
    DocumentViewResponse,
    UploadResponse,
)
from app.schemas.task import TaskDetailResponse, TaskListResponse
from app.services.task_manager import TaskManager
from app.services.task_store import TaskStore


router = APIRouter(tags=["tasks"])


@router.get("/tasks", response_model=TaskListResponse)
async def list_tasks(settings: Settings = Depends(get_settings)) -> TaskListResponse:
    store = TaskStore(settings.tasks_file)
    return store.list_tasks()


@router.get("/task/{task_id}", response_model=TaskDetailResponse)
async def get_task(task_id: str, settings: Settings = Depends(get_settings)) -> TaskDetailResponse:
    store = TaskStore(settings.tasks_file)
    task = store.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("/upload", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    settings: Settings = Depends(get_settings),
) -> UploadResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing uploaded file name")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    task_id = str(uuid4())
    input_path = settings.uploads_dir / f"{task_id}-{Path(file.filename).name}"
    input_path.write_bytes(file_bytes)

    doc_name = Path(file.filename).stem
    store = TaskStore(settings.tasks_file)
    task = store.create_task(
        task_id=task_id,
        title=doc_name,
        kind="doc_translate",
        input_filename=file.filename,
        doc_name=doc_name,
    )
    TaskManager(settings).start_document_task(task_id, input_path, doc_name)
    return UploadResponse(task=task)


@router.get("/result/{doc_name}", response_model=DocumentResultResponse)
async def get_document_result(
    doc_name: str,
    settings: Settings = Depends(get_settings),
) -> DocumentResultResponse:
    result_path = settings.outputs_dir / doc_name / f"{doc_name}.bilingual.json"
    if not result_path.exists():
        raise HTTPException(status_code=404, detail="Document result not found")

    return DocumentResultResponse.model_validate_json(result_path.read_text(encoding="utf-8"))


@router.get("/result/{doc_name}/{mode}", response_model=DocumentViewResponse)
async def get_document_result_view(
    doc_name: str,
    mode: str,
    settings: Settings = Depends(get_settings),
) -> DocumentViewResponse:
    result_path = settings.outputs_dir / doc_name / f"{doc_name}.bilingual.json"
    if not result_path.exists():
        raise HTTPException(status_code=404, detail="Document result not found")

    result = DocumentResultResponse.model_validate_json(result_path.read_text(encoding="utf-8"))
    allowed = {
        "english": result.english_markdown,
        "chinese": result.chinese_markdown,
        "bilingual": result.bilingual_markdown,
    }
    if mode not in allowed:
        raise HTTPException(status_code=400, detail="Unsupported mode")

    return DocumentViewResponse(doc_name=doc_name, mode=mode, content=allowed[mode])


@router.delete("/task/{task_id}")
async def delete_task(task_id: str, settings: Settings = Depends(get_settings)) -> dict[str, bool]:
    store = TaskStore(settings.tasks_file)
    deleted = store.delete_task(task_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"ok": True}
