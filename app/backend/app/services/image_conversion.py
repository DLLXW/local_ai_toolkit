import shutil
import subprocess
from pathlib import Path
from uuid import uuid4


HEIC_SUFFIXES = {".heic", ".heif"}
HEIC_MIME_TYPES = {"image/heic", "image/heif", "image/heic-sequence", "image/heif-sequence"}
RESIZABLE_SUFFIXES = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".heic", ".heif"}
RESIZABLE_MIME_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/tiff",
    "image/heic",
    "image/heif",
    "image/heic-sequence",
    "image/heif-sequence",
}


class ImageConversionError(ValueError):
    pass


def is_heic_image(*, content_type: str, filename: str) -> bool:
    return (
        (content_type or "").lower() in HEIC_MIME_TYPES
        or Path(filename).suffix.lower() in HEIC_SUFFIXES
    )


def is_resizable_image(*, content_type: str, filename: str) -> bool:
    return (
        (content_type or "").lower() in RESIZABLE_MIME_TYPES
        or Path(filename).suffix.lower() in RESIZABLE_SUFFIXES
    )


def prepare_image_for_ocr(
    *,
    file_bytes: bytes,
    content_type: str,
    filename: str,
    scratch_dir: Path,
    max_side: int,
) -> tuple[bytes, str, str]:
    should_convert_heic = is_heic_image(content_type=content_type, filename=filename)
    should_resize = max_side > 0 and is_resizable_image(content_type=content_type, filename=filename)
    if not should_convert_heic and not should_resize:
        return file_bytes, content_type, filename

    if shutil.which("sips") is None and should_convert_heic:
        raise ImageConversionError(
            "HEIC/HEIF images require macOS sips for conversion. Please convert the image to JPG or PNG first."
        )
    if shutil.which("sips") is None:
        return file_bytes, content_type, filename

    scratch_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(filename).stem or "image"
    input_suffix = Path(filename).suffix.lower() or ".jpg"
    output_suffix = ".jpg" if should_convert_heic else input_suffix
    output_content_type = "image/jpeg" if should_convert_heic else content_type
    output_filename = f"{stem}.jpg" if should_convert_heic else filename
    temp_id = uuid4().hex
    input_path = scratch_dir / f"{temp_id}-{stem}{input_suffix}"
    output_path = scratch_dir / f"{temp_id}-{stem}-prepared{output_suffix}"

    try:
        input_path.write_bytes(file_bytes)
        command = ["sips"]
        if should_convert_heic:
            command.extend(["-s", "format", "jpeg"])
        if should_resize:
            command.extend(["-Z", str(max_side)])
        command.extend([str(input_path), "--out", str(output_path)])
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0 or not output_path.exists():
            detail = (result.stderr or result.stdout or "unknown conversion error").strip()
            if should_convert_heic:
                raise ImageConversionError(f"Failed to convert HEIC/HEIF image to JPEG: {detail}")
            return file_bytes, content_type, filename
        return output_path.read_bytes(), output_content_type, output_filename
    finally:
        input_path.unlink(missing_ok=True)
        output_path.unlink(missing_ok=True)


def convert_heic_to_jpeg_if_needed(
    *,
    file_bytes: bytes,
    content_type: str,
    filename: str,
    scratch_dir: Path,
) -> tuple[bytes, str, str]:
    return prepare_image_for_ocr(
        file_bytes=file_bytes,
        content_type=content_type,
        filename=filename,
        scratch_dir=scratch_dir,
        max_side=0,
    )
