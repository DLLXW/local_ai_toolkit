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
