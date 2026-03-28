import time

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.core.settings import Settings, get_settings
from app.schemas.translate import TranslateRequest, TranslateResponse
from app.schemas.ocr import OCRResponse
from app.schemas.webpage import WebpageTranslateRequest, WebpageTranslateResponse
from app.services.ocr_service import OCRService
from app.services.translate_service import TranslateService
from app.services.webpage_service import WebpageService


router = APIRouter(tags=["tools"])


@router.post("/ocr", response_model=OCRResponse)
async def run_ocr(
    file: UploadFile = File(...),
    settings: Settings = Depends(get_settings),
) -> OCRResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing uploaded file name")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    try:
        service = OCRService(settings)
        return await service.recognize_file(
            file_bytes=file_bytes,
            content_type=file.content_type or "",
            filename=file.filename,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"OCR request failed: {exc}") from exc


@router.post("/translate", response_model=TranslateResponse)
async def run_translate(
    request: TranslateRequest,
    settings: Settings = Depends(get_settings),
) -> TranslateResponse:
    try:
        service = TranslateService(settings)
        return await service.translate(text=request.text, direction=request.direction)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Translation request failed: {exc}",
        ) from exc


@router.post("/webpage/translate", response_model=WebpageTranslateResponse)
async def translate_webpage(
    request: WebpageTranslateRequest,
    settings: Settings = Depends(get_settings),
) -> WebpageTranslateResponse:
    try:
        service = WebpageService(settings)
        started_at = time.perf_counter()
        payload = await service.translate_webpage(
            url=request.url,
            direction=request.direction,
        )
        payload.total_seconds = round(time.perf_counter() - started_at, 2)
        return payload
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Webpage translation failed: {exc}") from exc
