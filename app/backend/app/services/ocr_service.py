import base64
import json
import time
import urllib.request
from pathlib import Path
from uuid import uuid4

from app.core.settings import Settings
from app.schemas.ocr import OCRResponse
from app.services.glmocr_service import GLMOCRService


class OCRService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.glmocr = GLMOCRService()

    async def recognize_file(
        self,
        *,
        file_bytes: bytes,
        content_type: str,
        filename: str,
    ) -> OCRResponse:
        import asyncio

        return await asyncio.to_thread(
            self._recognize_file_sync,
            file_bytes=file_bytes,
            content_type=content_type,
            filename=filename,
        )

    def _recognize_file_sync(
        self,
        *,
        file_bytes: bytes,
        content_type: str,
        filename: str,
    ) -> OCRResponse:
        if self._is_pdf(content_type=content_type, filename=filename):
            return self._recognize_pdf_sync(file_bytes=file_bytes, filename=filename)

        started_at = time.perf_counter()
        mime = content_type or self._guess_mime(filename)
        encoded = base64.b64encode(file_bytes).decode("utf-8")
        data_uri = f"data:{mime};base64,{encoded}"
        payload = {
            "model": self.settings.ocr_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": self.settings.ocr_prompt},
                        {"type": "image_url", "image_url": {"url": data_uri}},
                    ],
                }
            ],
            "max_tokens": 4096,
            "temperature": 0.1,
        }

        url = f"{self.settings.ocr_base_url.rstrip('/')}{self.settings.ocr_chat_path}"
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=self.settings.ocr_timeout_seconds) as response:
            raw_response = json.loads(response.read().decode("utf-8"))

        content = self._extract_content(raw_response)
        return OCRResponse(
            markdown=content,
            raw_text=content,
            model=self.settings.ocr_model,
            provider_url=url,
            raw_response=raw_response,
            elapsed_seconds=round(time.perf_counter() - started_at, 2),
        )

    def _recognize_pdf_sync(self, *, file_bytes: bytes, filename: str) -> OCRResponse:
        started_at = time.perf_counter()
        doc_stem = Path(filename).stem or "document"
        safe_name = self._safe_doc_name(f"{doc_stem}-{uuid4().hex[:8]}")
        input_path = self.settings.uploads_dir / f"{safe_name}.pdf"
        output_dir = self.settings.outputs_dir / safe_name

        try:
            input_path.write_bytes(file_bytes)
            markdown, ocr_json = self.glmocr.parse(input_path=input_path, output_dir=output_dir)
            return OCRResponse(
                markdown=markdown,
                raw_text=markdown,
                model="glmocr-cli",
                provider_url=str(self.glmocr.glmocr_cli),
                raw_response={
                    "source": "glmocr_cli",
                    "doc_name": safe_name,
                    "ocr_json": ocr_json,
                },
                elapsed_seconds=round(time.perf_counter() - started_at, 2),
            )
        finally:
            input_path.unlink(missing_ok=True)

    @staticmethod
    def _extract_content(raw_response: dict) -> str:
        choices = raw_response.get("choices") or []
        if not choices:
            raise ValueError("OCR service returned no choices")
        message = choices[0].get("message") or {}
        content = message.get("content")
        if not isinstance(content, str):
            raise ValueError("OCR service returned invalid message content")
        return content.strip()

    @staticmethod
    def _guess_mime(filename: str) -> str:
        lower_name = filename.lower()
        if lower_name.endswith(".png"):
            return "image/png"
        if lower_name.endswith(".pdf"):
            return "application/pdf"
        if lower_name.endswith(".webp"):
            return "image/webp"
        return "image/jpeg"

    @staticmethod
    def _is_pdf(*, content_type: str, filename: str) -> bool:
        return "pdf" in (content_type or "").lower() or filename.lower().endswith(".pdf")

    @staticmethod
    def _safe_doc_name(name: str) -> str:
        import re

        collapsed = re.sub(r"\s+", "-", name.strip())
        safe = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff._-]", "", collapsed)
        return safe or "document"
