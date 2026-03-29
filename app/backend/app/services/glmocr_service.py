import json
import shutil
import subprocess
from pathlib import Path


class GLMOCRService:
    def __init__(self) -> None:
        self.root_dir = Path(__file__).resolve().parents[4]
        self.glmocr_cli = self.root_dir / "glm-ocr" / ".venv" / "bin" / "glmocr"

    def parse(self, *, input_path: Path, output_dir: Path) -> tuple[str, list]:
        if not self.glmocr_cli.exists():
            raise FileNotFoundError(f"GLM-OCR CLI not found: {self.glmocr_cli}")

        output_dir.mkdir(parents=True, exist_ok=True)
        cmd = [str(self.glmocr_cli), "parse", str(input_path), "--output", str(output_dir)]
        subprocess.run(
            cmd,
            cwd=self.root_dir / "glm-ocr",
            check=True,
            capture_output=True,
            text=True,
        )

        markdown = self._read_output_file(output_dir, ".md")
        ocr_json = json.loads(self._read_output_file(output_dir, ".json"))
        self._sync_assets(output_dir)
        return markdown, ocr_json

    def _read_output_file(self, output_dir: Path, suffix: str) -> str:
        matches = sorted(output_dir.rglob(f"*{suffix}"))
        if not matches:
            raise FileNotFoundError(f"Missing GLM-OCR output (*{suffix}) in {output_dir}")
        return matches[0].read_text(encoding="utf-8")

    def _sync_assets(self, output_dir: Path) -> None:
        nested_dirs = [path.parent for path in output_dir.rglob("*.md") if path.parent != output_dir]
        for nested_dir in nested_dirs:
            for folder_name in ("imgs", "layout_vis", "images"):
                src_dir = nested_dir / folder_name
                dst_dir = output_dir / folder_name
                if src_dir.exists() and src_dir.is_dir():
                    shutil.copytree(src_dir, dst_dir, dirs_exist_ok=True)
