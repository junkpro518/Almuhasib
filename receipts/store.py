import re
import shutil
from pathlib import Path

from config import RECEIPTS_DIR

_SAFE_EXTENSIONS = {
    "jpg": ".jpg",
    "jpeg": ".jpg",
    "png": ".png",
    "webp": ".webp",
}


def _safe_page_id(page_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "-", page_id)


def _receipt_dir() -> Path:
    path = Path(RECEIPTS_DIR)
    path.mkdir(parents=True, exist_ok=True)
    return path


def normalize_extension(file_path: str | None, mime_type: str | None = None) -> str:
    suffix = Path(file_path or "").suffix.lower().lstrip(".")
    if suffix in _SAFE_EXTENSIONS:
        return _SAFE_EXTENSIONS[suffix]
    if mime_type:
        subtype = mime_type.split("/", 1)[-1].lower()
        if subtype in _SAFE_EXTENSIONS:
            return _SAFE_EXTENSIONS[subtype]
    return ".jpg"


def receipt_path_for_page(page_id: str) -> Path | None:
    prefix = _safe_page_id(page_id)
    for path in sorted(_receipt_dir().glob(f"{prefix}.*")):
        if path.is_file():
            return path
    return None


def save_receipt(page_id: str, source_path: str | Path, extension: str) -> Path:
    extension = extension if extension.startswith(".") else f".{extension}"
    target = _receipt_dir() / f"{_safe_page_id(page_id)}{extension.lower()}"
    shutil.copyfile(source_path, target)
    return target


def clear_receipts() -> int:
    count = 0
    directory = _receipt_dir()
    for path in directory.iterdir():
        if path.is_file():
            path.unlink()
            count += 1
    return count
