import re
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.core.settings import Settings, get_settings
from app.schemas.document import (
    DocumentResultResponse,
    DocumentViewResponse,
    UploadResponse,
    UrlUploadRequest,
)
from app.schemas.task import TaskDetailResponse, TaskListResponse
from app.schemas.task import TaskUpdateRequest
from app.services.task_manager import TaskManager
from app.services.task_store import TaskStore


router = APIRouter(tags=["tasks"])

ARXIV_HOSTS = {"arxiv.org", "www.arxiv.org"}


def _resolve_asset_base_url(settings: Settings, doc_name: str) -> str | None:
    doc_dir = settings.outputs_dir / doc_name
    if not doc_dir.exists():
        return None

    direct_imgs = doc_dir / "imgs"
    if direct_imgs.exists():
        return f"/static/outputs/{doc_name}/imgs"

    candidates = sorted(
        [path for path in doc_dir.rglob("imgs") if path.is_dir()],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        return None

    relative = candidates[0].relative_to(settings.outputs_dir).as_posix()
    return f"/static/outputs/{relative}"


def _create_document_task(
    *,
    settings: Settings,
    input_path: Path,
    input_filename: str,
    doc_name: str,
    title: str | None = None,
) -> UploadResponse:
    task_id = str(uuid4())
    store = TaskStore(settings.tasks_file)
    task = store.create_task(
        task_id=task_id,
        title=title or doc_name,
        kind="doc_translate",
        input_filename=input_filename,
        doc_name=doc_name,
    )
    TaskManager(settings).start_document_task(task_id, input_path, doc_name)
    return UploadResponse(task=task)


def _normalize_arxiv_url(raw_url: str) -> tuple[str, str]:
    url = raw_url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="Missing paper url")

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or parsed.netloc not in ARXIV_HOSTS:
        raise HTTPException(status_code=400, detail="Currently only arXiv links are supported")

    path = parsed.path.rstrip("/")
    if path.startswith("/abs/"):
        paper_id = path.removeprefix("/abs/")
        return f"https://arxiv.org/pdf/{paper_id}.pdf", paper_id

    if path.startswith("/pdf/"):
        paper_id = path.removeprefix("/pdf/")
        if paper_id.endswith(".pdf"):
            paper_id = paper_id[:-4]
        return f"https://arxiv.org/pdf/{paper_id}.pdf", paper_id

    raise HTTPException(status_code=400, detail="Unsupported arXiv link format")


def _safe_arxiv_doc_name(paper_id: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z._-]+", "-", paper_id.strip())
    return cleaned.strip("-") or "arxiv-paper"


def _clean_display_title(value: str | None, fallback: str) -> str:
    title = re.sub(r"\s+", " ", (value or "").strip())
    return title or fallback


def _extract_arxiv_title(html: str) -> str | None:
    meta_match = re.search(
        r'<meta\s+name="citation_title"\s+content="([^"]+)"',
        html,
        flags=re.IGNORECASE,
    )
    if meta_match:
        return meta_match.group(1).strip()

    title_match = re.search(r"<title>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
    if title_match:
        title = re.sub(r"\s+", " ", title_match.group(1)).strip()
        title = re.sub(r"\s*\|\s*arXiv.*$", "", title, flags=re.IGNORECASE)
        return title

    return None


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

    input_path = settings.uploads_dir / f"{uuid4()}-{Path(file.filename).name}"
    input_path.write_bytes(file_bytes)

    doc_name = Path(file.filename).stem
    return _create_document_task(
        settings=settings,
        input_path=input_path,
        input_filename=file.filename,
        doc_name=doc_name,
        title=_clean_display_title(doc_name, doc_name),
    )


@router.post("/upload/url", response_model=UploadResponse)
async def upload_document_from_url(
    payload: UrlUploadRequest,
    settings: Settings = Depends(get_settings),
) -> UploadResponse:
    pdf_url, paper_id = _normalize_arxiv_url(payload.url)
    abs_url = f"https://arxiv.org/abs/{paper_id}"
    filename = f"{paper_id}.pdf"
    input_path = settings.uploads_dir / f"{uuid4()}-{filename}"
    paper_title: str | None = None

    try:
        async with httpx.AsyncClient(timeout=180.0, follow_redirects=True) as client:
            abs_response = await client.get(
                abs_url,
                headers={"User-Agent": "Local AI Toolkit/0.1"},
            )
            if abs_response.is_success:
                paper_title = _extract_arxiv_title(abs_response.text)
            response = await client.get(
                pdf_url,
                headers={"User-Agent": "Local AI Toolkit/0.1"},
            )
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=400, detail=f"Failed to download arXiv PDF: {exc}") from exc

    content_type = response.headers.get("content-type", "")
    if "pdf" not in content_type.lower() and not response.content.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="Downloaded content is not a PDF")

    input_path.write_bytes(response.content)
    return _create_document_task(
        settings=settings,
        input_path=input_path,
        input_filename=filename,
        doc_name=_safe_arxiv_doc_name(paper_id),
        title=_clean_display_title(paper_title, paper_id),
    )


@router.patch("/task/{task_id}", response_model=TaskDetailResponse)
async def update_task(
    task_id: str,
    payload: TaskUpdateRequest,
    settings: Settings = Depends(get_settings),
) -> TaskDetailResponse:
    changes: dict[str, object] = {}
    if payload.title is not None:
        title = _clean_display_title(payload.title, "")
        if not title:
            raise HTTPException(status_code=400, detail="Title cannot be empty")
        changes["title"] = title
    if payload.folder_name is not None:
        folder_name = _clean_display_title(payload.folder_name, "未分类")
        changes["folder_name"] = folder_name

    if not changes:
        raise HTTPException(status_code=400, detail="No task changes provided")

    store = TaskStore(settings.tasks_file)
    try:
        task = store.update_task(task_id, **changes)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Task not found") from exc
    return TaskDetailResponse(task=task)


@router.get("/result/{doc_name}", response_model=DocumentResultResponse)
async def get_document_result(
    doc_name: str,
    settings: Settings = Depends(get_settings),
) -> DocumentResultResponse:
    result_path = settings.outputs_dir / doc_name / f"{doc_name}.bilingual.json"
    if not result_path.exists():
        raise HTTPException(status_code=404, detail="Document result not found")

    result = DocumentResultResponse.model_validate_json(result_path.read_text(encoding="utf-8"))
    result.asset_base_url = _resolve_asset_base_url(settings, doc_name)
    return result


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
