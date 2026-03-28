import re
import time

import httpx

from app.core.settings import Settings
from app.schemas.translate import TranslateDirection, TranslateResponse


TRANSLATE_PROMPTS: dict[TranslateDirection, str] = {
    "en2zh": (
        "You are a translation engine. Translate the following English text into "
        "natural, faithful Chinese. Output only the final translation."
    ),
    "zh2en": (
        "You are a translation engine. Translate the following Chinese text into "
        "natural, faithful English. Output only the final translation."
    ),
}


class TranslateService:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def translate(
        self,
        *,
        text: str,
        direction: TranslateDirection,
    ) -> TranslateResponse:
        prompt = TRANSLATE_PROMPTS[direction]
        user_content = f"{prompt}\n\n{text}"
        payload = {
            "messages": [{"role": "user", "content": user_content}],
            "max_tokens": 2048,
            "temperature": 0.1,
        }
        if self.settings.translate_model:
            payload["model"] = self.settings.translate_model

        url = (
            f"{self.settings.translate_base_url.rstrip('/')}"
            f"{self.settings.translate_chat_path}"
        )
        async with httpx.AsyncClient(
            timeout=self.settings.translate_timeout_seconds
        ) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            raw_response = response.json()

        content = self._extract_content(raw_response)
        return TranslateResponse(
            direction=direction,
            source_text=text,
            translated_text=content,
            model=self.settings.translate_model or "default",
            provider_url=url,
            raw_response=raw_response,
        )

    async def translate_long_text(
        self,
        *,
        text: str,
        direction: TranslateDirection,
    ) -> TranslateResponse:
        prompt = TRANSLATE_PROMPTS[direction]
        url = (
            f"{self.settings.translate_base_url.rstrip('/')}"
            f"{self.settings.translate_chat_path}"
        )
        started_at = time.perf_counter()
        async with httpx.AsyncClient(
            timeout=self.settings.translate_timeout_seconds
        ) as client:
            chunks = self._chunk_text(text)
            raw_responses: list[dict] = []
            translated_chunks: list[str] = []
            for chunk in chunks:
                payload = {
                    "messages": [{"role": "user", "content": f"{prompt}\n\n{chunk}"}],
                    "max_tokens": 2048,
                    "temperature": 0.1,
                }
                if self.settings.translate_model:
                    payload["model"] = self.settings.translate_model
                response = await client.post(url, json=payload)
                response.raise_for_status()
                raw_response = response.json()
                raw_responses.append(raw_response)
                translated_chunks.append(self._extract_content(raw_response))

        return TranslateResponse(
            direction=direction,
            source_text=text,
            translated_text="\n\n".join(part for part in translated_chunks if part.strip()).strip(),
            model=self.settings.translate_model or "default",
            provider_url=url,
            raw_response={
                "chunks": len(chunks),
                "responses": raw_responses,
                "elapsed_seconds": round(time.perf_counter() - started_at, 2),
            },
        )

    @staticmethod
    def _extract_content(raw_response: dict) -> str:
        choices = raw_response.get("choices") or []
        if not choices:
            raise ValueError("Translation service returned no choices")
        message = choices[0].get("message") or {}
        content = message.get("content")
        if not isinstance(content, str):
            raise ValueError("Translation service returned invalid message content")
        return content.strip()

    def _chunk_text(self, text: str) -> list[str]:
        max_chars = self.settings.translate_max_chars_per_chunk
        if len(text) <= max_chars:
            return [text]

        lines = [line.rstrip() for line in text.splitlines()]
        parts: list[str] = []
        current = ""
        for line in lines:
            candidate = line if not current else f"{current}\n{line}"
            if len(candidate) <= max_chars:
                current = candidate
                continue
            if current.strip():
                parts.append(current.strip())
            if len(line) <= max_chars:
                current = line
            else:
                parts.extend(self._split_long_line(line, max_chars))
                current = ""
        if current.strip():
            parts.append(current.strip())
        return parts or [text]

    @staticmethod
    def _split_long_line(line: str, max_chars: int) -> list[str]:
        segments = re.split(r"(?<=[\.\!\?;:。！？；：])\s+", line)
        parts: list[str] = []
        current = ""
        for segment in segments:
            segment = segment.strip()
            if not segment:
                continue
            candidate = segment if not current else f"{current} {segment}"
            if len(candidate) <= max_chars:
                current = candidate
                continue
            if current:
                parts.append(current)
            current = segment
        if current:
            parts.append(current)
        return parts
