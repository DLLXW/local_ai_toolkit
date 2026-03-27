import base64
import json
import time
import urllib.request

from app.core.settings import Settings
from app.schemas.ocr import OCRResponse


class OCRService:
    def __init__(self, settings: Settings):
        self.settings = settings

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
