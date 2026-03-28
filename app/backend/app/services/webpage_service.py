import re
import time
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from bs4.element import Tag

from app.core.settings import Settings
from app.schemas.translate import TranslateDirection
from app.schemas.webpage import WebpageTranslateResponse
from app.services.translate_service import TranslateService


class WebpageService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.translate_service = TranslateService(settings)

    async def translate_webpage(
        self,
        *,
        url: str,
        direction: TranslateDirection,
    ) -> WebpageTranslateResponse:
        started_at = time.perf_counter()
        normalized_url = self._normalize_url(url)

        fetch_started_at = time.perf_counter()
        html, ssl_fallback_used = await self._fetch_html(normalized_url)
        fetch_seconds = round(time.perf_counter() - fetch_started_at, 2)

        title, source_markdown = self._extract_readable_markdown(html, normalized_url)
        translation_started_at = time.perf_counter()
        translated = await self.translate_service.translate_long_text(
            text=source_markdown,
            direction=direction,
        )
        translation_seconds = round(time.perf_counter() - translation_started_at, 2)

        return WebpageTranslateResponse(
            url=normalized_url,
            title=title,
            source_markdown=source_markdown,
            translated_markdown=translated.translated_text,
            source_excerpt=source_markdown[:240],
            ssl_fallback_used=ssl_fallback_used,
            fetch_seconds=fetch_seconds,
            translation_seconds=translation_seconds,
            total_seconds=round(time.perf_counter() - started_at, 2),
        )

    async def _fetch_html(self, url: str) -> tuple[str, bool]:
        headers = {
            "User-Agent": "Local AI Toolkit/0.1",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        try:
            async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                return response.text, False
        except httpx.ConnectError as exc:
            if "CERTIFICATE_VERIFY_FAILED" not in str(exc):
                raise

        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True, verify=False) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.text, True

    @staticmethod
    def _normalize_url(url: str) -> str:
        candidate = url.strip()
        parsed = urlparse(candidate)
        if not parsed.scheme:
            candidate = f"https://{candidate}"
            parsed = urlparse(candidate)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Invalid webpage url")
        return candidate

    def _extract_readable_markdown(self, html: str, url: str) -> tuple[str, str]:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "aside", "form"]):
            tag.decompose()

        title = self._extract_title(soup, url)
        root = soup.find("main") or soup.find("article") or soup.body or soup

        blocks: list[str] = []
        for node in root.find_all(
            ["h1", "h2", "h3", "h4", "p", "li", "pre", "blockquote", "img"],
            recursive=True,
        ):
            block = self._node_to_markdown(node, url)
            if not block:
                continue
            blocks.append(block)

        markdown = "\n\n".join(self._dedupe_blocks(blocks)).strip()
        if not markdown:
            markdown = self._normalize_text((soup.body or soup).get_text("\n", strip=True))
        return title, markdown

    def _node_to_markdown(self, node: Tag, base_url: str) -> str:
        if node.name == "img":
            src = self._resolve_src(node, base_url)
            if not src:
                return ""
            alt = self._normalize_text(node.get("alt", "") or "image")
            return f"![{alt}]({src})"

        text = self._extract_text_with_links(node, base_url)
        if len(text) < 25 and node.name == "p":
            return ""
        if not text:
            return ""
        if node.name.startswith("h"):
            level = int(node.name[1])
            return f"{'#' * level} {text}"
        if node.name == "li":
            return f"- {text}"
        if node.name == "blockquote":
            return f"> {text}"
        if node.name == "pre":
            return f"```\n{text}\n```"
        return text

    def _extract_text_with_links(self, node: Tag, base_url: str) -> str:
        clone = BeautifulSoup(str(node), "html.parser")
        current = clone.find(node.name) or clone

        for anchor in current.find_all("a"):
            label = self._normalize_text(anchor.get_text(" ", strip=True))
            href = urljoin(base_url, anchor.get("href", "").strip()) if anchor.get("href") else ""
            replacement = f"[{label}]({href})" if label and href else label
            anchor.replace_with(replacement)

        return self._normalize_text(current.get_text(" ", strip=True))

    @staticmethod
    def _resolve_src(node: Tag, base_url: str) -> str:
        src = (node.get("src") or "").strip()
        if not src:
            return ""
        return urljoin(base_url, src)

    @staticmethod
    def _extract_title(soup: BeautifulSoup, url: str) -> str:
        for selector in (
            ("meta", {"property": "og:title"}),
            ("meta", {"name": "twitter:title"}),
        ):
            tag = soup.find(selector[0], attrs=selector[1])
            content = tag.get("content") if tag else None
            if content:
                return re.sub(r"\s+", " ", content).strip()

        if soup.title and soup.title.string:
            return re.sub(r"\s+", " ", soup.title.string).strip()

        return urlparse(url).netloc

    @staticmethod
    def _normalize_text(text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _dedupe_blocks(blocks: list[str]) -> list[str]:
        deduped: list[str] = []
        previous = None
        for block in blocks:
            if block == previous:
                continue
            deduped.append(block)
            previous = block
        return deduped
