from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT_DIR / "data"


class Settings(BaseSettings):
    app_name: str = "Local AI Toolkit Backend"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    debug: bool = True

    ocr_base_url: str = "http://127.0.0.1:8080"
    ocr_chat_path: str = "/chat/completions"
    ocr_model: str = "mlx-community/GLM-OCR-bf16"
    ocr_timeout_seconds: float = 180.0
    ocr_prompt: str = (
        "Recognize the text in the image and output in Markdown format. "
        "Preserve headings, paragraphs, tables, and formulas."
    )

    translate_base_url: str = "http://127.0.0.1:8090"
    translate_chat_path: str = "/v1/chat/completions"
    translate_model: str | None = None
    translate_timeout_seconds: float = 120.0
    translate_retry_attempts: int = 3
    translate_retry_backoff_seconds: float = 1.5
    translate_max_chars_per_chunk: int = 900

    tasks_file: Path = Field(default=DATA_DIR / "tasks.json")
    uploads_dir: Path = Field(default=DATA_DIR / "uploads")
    outputs_dir: Path = Field(default=DATA_DIR / "outputs")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="LOCAL_AI_",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    settings.outputs_dir.mkdir(parents=True, exist_ok=True)
    settings.tasks_file.parent.mkdir(parents=True, exist_ok=True)
    return settings
