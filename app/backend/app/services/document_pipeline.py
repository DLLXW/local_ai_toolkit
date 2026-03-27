import json
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import httpx

from app.core.settings import Settings


UpdateCallback = Callable[[dict], None]


@dataclass
class PipelineArtifacts:
    doc_name: str
    english_markdown: str
    chinese_markdown: str
    bilingual_markdown: str
    segments: list[dict]
    ocr_json: list
    output_dir: Path


class DocumentPipeline:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.root_dir = Path(__file__).resolve().parents[4]
        self.glmocr_cli = self.root_dir / "glm-ocr" / ".venv" / "bin" / "glmocr"

    def run(
        self,
        input_path: Path,
        *,
        doc_name: str | None = None,
        update: UpdateCallback | None = None,
    ) -> PipelineArtifacts:
        doc_name = self._safe_doc_name(doc_name or input_path.stem)
        output_dir = self.settings.outputs_dir / doc_name
        output_dir.mkdir(parents=True, exist_ok=True)

        self._emit(update, status="running", progress=0.1, step="ocr_running")
        self._run_glmocr(input_path=input_path, output_dir=output_dir)

        self._emit(update, status="running", progress=0.45, step="ocr_loaded")
        english_markdown = self._read_output_file(output_dir, ".md")
        ocr_json = json.loads(self._read_output_file(output_dir, ".json"))
        self._sync_assets(output_dir)

        self._emit(update, status="running", progress=0.55, step="translation_running")
        segments = self._split_markdown(english_markdown)
        translated_segments = self._translate_segments(segments)

        chinese_markdown = "\n\n".join(segment["target"] for segment in translated_segments).strip()
        bilingual_markdown = "\n\n".join(
            self._render_bilingual_segment(segment) for segment in translated_segments
        ).strip()

        artifacts = {
            "doc_name": doc_name,
            "english_markdown": english_markdown,
            "chinese_markdown": chinese_markdown,
            "bilingual_markdown": bilingual_markdown,
            "segments": translated_segments,
            "ocr_json": ocr_json,
        }
        (output_dir / f"{doc_name}.zh.md").write_text(chinese_markdown, encoding="utf-8")
        (output_dir / f"{doc_name}.bilingual.md").write_text(
            bilingual_markdown,
            encoding="utf-8",
        )
        (output_dir / f"{doc_name}.bilingual.json").write_text(
            json.dumps(artifacts, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        self._emit(update, status="done", progress=1.0, step="completed")
        return PipelineArtifacts(
            doc_name=doc_name,
            english_markdown=english_markdown,
            chinese_markdown=chinese_markdown,
            bilingual_markdown=bilingual_markdown,
            segments=translated_segments,
            ocr_json=ocr_json,
            output_dir=output_dir,
        )

    def _run_glmocr(self, *, input_path: Path, output_dir: Path) -> None:
        if not self.glmocr_cli.exists():
            raise FileNotFoundError(f"GLM-OCR CLI not found: {self.glmocr_cli}")

        cmd = [str(self.glmocr_cli), "parse", str(input_path), "--output", str(output_dir)]
        subprocess.run(
            cmd,
            cwd=self.root_dir / "glm-ocr",
            check=True,
            capture_output=True,
            text=True,
        )

    def _translate_segments(self, segments: list[dict]) -> list[dict]:
        translated: list[dict] = []
        url = (
            f"{self.settings.translate_base_url.rstrip('/')}"
            f"{self.settings.translate_chat_path}"
        )
        cache: dict[str, str] = {}
        with httpx.Client(timeout=self.settings.translate_timeout_seconds) as client:
            for segment in segments:
                if segment["kind"] != "text":
                    translated.append({**segment, "target": segment["source"]})
                    continue

                source = segment["source"]
                if source in cache:
                    target = cache[source]
                else:
                    target = self._translate_text_with_fallback(
                        client=client,
                        url=url,
                        text=source,
                    )
                    cache[source] = target

                translated.append({**segment, "target": target})
        return translated

    def _translate_text_with_fallback(
        self,
        *,
        client: httpx.Client,
        url: str,
        text: str,
    ) -> str:
        chunks = self._chunk_text(text)
        translated_chunks = [
            self._translate_chunk_with_retry(client=client, url=url, text=chunk)
            for chunk in chunks
        ]
        return "\n\n".join(chunk for chunk in translated_chunks if chunk.strip()).strip()

    def _translate_chunk_with_retry(
        self,
        *,
        client: httpx.Client,
        url: str,
        text: str,
    ) -> str:
        last_error: Exception | None = None
        for attempt in range(self.settings.translate_retry_attempts):
            try:
                payload = {
                    "messages": [
                        {
                            "role": "user",
                            "content": (
                                "Translate the following English markdown into natural Chinese. "
                                "Keep markdown structure when present. Output only the translation.\n\n"
                                f"{text}"
                            ),
                        }
                    ],
                    "max_tokens": 1024,
                    "temperature": 0.1,
                }
                if self.settings.translate_model:
                    payload["model"] = self.settings.translate_model

                response = client.post(url, json=payload)
                response.raise_for_status()
                raw = response.json()
                choices = raw.get("choices") or []
                if not choices:
                    raise ValueError("Translation service returned no choices")
                content = (choices[0].get("message") or {}).get("content", "").strip()
                if not content:
                    raise ValueError("Translation service returned empty content")
                return content
            except Exception as exc:
                last_error = exc
                if attempt < self.settings.translate_retry_attempts - 1:
                    time.sleep(self.settings.translate_retry_backoff_seconds * (attempt + 1))
                    continue
        assert last_error is not None
        raise last_error

    def _split_markdown(self, markdown: str) -> list[dict]:
        blocks = self._merge_semantic_blocks(self._extract_markdown_blocks(markdown))
        segments: list[dict] = []
        for block in blocks:
            kind = "raw" if self._is_raw_block(block) else "text"
            segments.append({"kind": kind, "source": block})
        return segments

    def _extract_markdown_blocks(self, markdown: str) -> list[str]:
        blocks: list[str] = []
        lines = markdown.splitlines()
        current: list[str] = []
        in_fence = False
        in_html_table = False

        def flush_current() -> None:
            nonlocal current
            block = "\n".join(current).strip()
            if block:
                blocks.append(block)
            current = []

        for line in lines:
            stripped = line.strip()

            if in_fence:
                current.append(line)
                if stripped.startswith("```"):
                    flush_current()
                    in_fence = False
                continue

            if in_html_table:
                current.append(line)
                if "</table>" in stripped.lower():
                    flush_current()
                    in_html_table = False
                continue

            if not stripped:
                flush_current()
                continue

            if stripped.startswith("```"):
                flush_current()
                current.append(line)
                in_fence = True
                continue

            if stripped.lower().startswith("<table"):
                flush_current()
                current.append(line)
                if "</table>" in stripped.lower():
                    flush_current()
                else:
                    in_html_table = True
                continue

            if self._is_standalone_raw_line(stripped):
                flush_current()
                blocks.append(stripped)
                continue

            current.append(line)

        flush_current()
        return blocks

    def _merge_semantic_blocks(self, blocks: list[str]) -> list[str]:
        merged: list[str] = []
        pending: list[str] = []

        def flush_pending() -> None:
            nonlocal pending
            block = "\n\n".join(part.strip() for part in pending if part.strip()).strip()
            if block:
                merged.append(block)
            pending = []

        for block in blocks:
            if self._is_raw_block(block):
                flush_pending()
                merged.append(block)
                continue

            if self._is_heading_block(block):
                flush_pending()
                pending = [block]
                continue

            if pending:
                pending.append(block)
                continue

            pending = [block]
            flush_pending()

        flush_pending()
        return merged

    @staticmethod
    def _is_standalone_raw_line(line: str) -> bool:
        return (
            line.startswith("|")
            or "![](" in line
            or "$$" in line
            or "\\[" in line
            or "\\begin{" in line
        )

    @staticmethod
    def _is_raw_block(block: str) -> bool:
        stripped = block.strip()
        return (
            stripped.startswith("```")
            or stripped.startswith("|")
            or stripped.lower().startswith("<table")
            or "![](" in stripped
            or "$$" in stripped
            or "\\[" in stripped
            or "\\begin{" in stripped
        )

    @staticmethod
    def _is_heading_block(block: str) -> bool:
        return bool(re.match(r"^#{1,6}\s", block.strip()))

    def _chunk_text(self, text: str) -> list[str]:
        max_chars = self.settings.translate_max_chars_per_chunk
        if len(text) <= max_chars:
            return [text]

        lines = [line.strip() for line in text.splitlines()]
        parts: list[str] = []
        current = ""

        for line in lines:
            if not line:
                if current.strip():
                    current = f"{current}\n"
                continue

            for sentence in self._split_line_into_sentences(line):
                candidate = sentence if not current else f"{current}\n{sentence}"
                if len(candidate) <= max_chars:
                    current = candidate
                    continue

                if current.strip():
                    parts.append(current.strip())
                    current = ""

                if len(sentence) <= max_chars:
                    current = sentence
                else:
                    parts.extend(self._force_split_long_sentence(sentence, max_chars))

        if current.strip():
            parts.append(current.strip())
        return parts or [text]

    @staticmethod
    def _split_line_into_sentences(line: str) -> list[str]:
        chunks = re.split(r"(?<=[\.\!\?;。！？；:])\s+", line)
        return [chunk.strip() for chunk in chunks if chunk.strip()]

    @staticmethod
    def _force_split_long_sentence(sentence: str, max_chars: int) -> list[str]:
        words = sentence.split(" ")
        if len(words) == 1:
            return [
                sentence[i : i + max_chars].strip()
                for i in range(0, len(sentence), max_chars)
                if sentence[i : i + max_chars].strip()
            ]

        parts: list[str] = []
        current = ""
        for word in words:
            candidate = word if not current else f"{current} {word}"
            if len(candidate) <= max_chars:
                current = candidate
                continue
            if current:
                parts.append(current)
            current = word
        if current:
            parts.append(current)
        return parts

    def _read_output_file(self, output_dir: Path, suffix: str) -> str:
        candidates = sorted(output_dir.rglob(f"*{suffix}"))
        if not candidates:
            raise FileNotFoundError(f"No {suffix} file found in {output_dir}")
        return candidates[0].read_text(encoding="utf-8")

    def _sync_assets(self, output_dir: Path) -> None:
        nested_dirs = [path.parent for path in output_dir.rglob("*.md") if path.parent != output_dir]
        for nested_dir in nested_dirs:
            for folder_name in ("imgs", "layout_vis"):
                src_dir = nested_dir / folder_name
                dst_dir = output_dir / folder_name
                if src_dir.exists() and src_dir.is_dir():
                    shutil.copytree(src_dir, dst_dir, dirs_exist_ok=True)

    @staticmethod
    def _render_bilingual_segment(segment: dict) -> str:
        if segment["kind"] != "text":
            return segment["source"]
        return "\n".join(
            [
                "::: bilingual",
                segment["source"],
                "---",
                segment["target"],
                ":::",
            ]
        )

    @staticmethod
    def _emit(update: UpdateCallback | None, **changes: object) -> None:
        if update is not None:
            update(changes)

    @staticmethod
    def _safe_doc_name(name: str) -> str:
        collapsed = re.sub(r"\s+", "-", name.strip())
        safe = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff._-]", "", collapsed)
        return safe or "document"
