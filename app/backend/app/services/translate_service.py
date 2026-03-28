import asyncio
import re

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

RETRY_PROMPTS: dict[TranslateDirection, str] = {
    "en2zh": (
        "Translate the source text into simplified Chinese only. "
        "Do not copy the original English. "
        "Do not explain. Output only the Chinese translation."
    ),
    "zh2en": (
        "Translate the source text into English only. "
        "Do not copy the original Chinese. "
        "Do not explain. Output only the English translation."
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
        async with httpx.AsyncClient(timeout=self.settings.translate_timeout_seconds) as client:
            raw_response = await self._request_translation(
                client=client,
                url=url,
                text=text,
                direction=direction,
            )

        content = self._extract_content(raw_response)
        return TranslateResponse(
            direction=direction,
            source_text=text,
            translated_text=content,
            model=self.settings.translate_model or "default",
            provider_url=url,
            raw_response=raw_response,
        )

    async def _request_translation(
        self,
        *,
        client: httpx.AsyncClient,
        url: str,
        text: str,
        direction: TranslateDirection,
    ) -> dict:
        prompt_variants = [TRANSLATE_PROMPTS[direction]]
        if self.settings.translate_retry_attempts > 1:
            prompt_variants.extend([RETRY_PROMPTS[direction]] * (self.settings.translate_retry_attempts - 1))

        last_response: dict | None = None
        for attempt, prompt in enumerate(prompt_variants):
            payload = {
                "messages": [
                    {"role": "system", "content": "You are a precise bilingual translation engine."},
                    {"role": "user", "content": f"{prompt}\n\nSource text:\n{text}"},
                ],
                "max_tokens": 2048,
                "temperature": 0.1,
            }
            if self.settings.translate_model:
                payload["model"] = self.settings.translate_model

            response = await client.post(url, json=payload)
            response.raise_for_status()
            raw_response = response.json()
            last_response = raw_response

            content = self._extract_content(raw_response)
            if self._looks_translated(content, direction):
                return raw_response

            if attempt < len(prompt_variants) - 1:
                await asyncio.sleep(self.settings.translate_retry_backoff_seconds)

        if last_response is None:
            raise ValueError("Translation service returned no response")
        return last_response

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

    @staticmethod
    def _looks_translated(content: str, direction: TranslateDirection) -> bool:
        normalized = content.strip()
        if not normalized:
            return False

        cjk_count = len(re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff]", normalized))
        latin_count = len(re.findall(r"[A-Za-z]", normalized))

        if direction == "zh2en":
            return latin_count > 0 and cjk_count <= max(1, len(normalized) // 12)

        return cjk_count > 0
