from __future__ import annotations

from pathlib import Path

from app.constants import ARCHIVE_EXTS, DOCUMENT_EXTS, IMAGE_EXTS, VIDEO_EXTS


def detect_file_type(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in IMAGE_EXTS:
        return "image"
    if ext in VIDEO_EXTS:
        return "video"
    if ext in DOCUMENT_EXTS:
        return "document"
    if ext in ARCHIVE_EXTS:
        return "archive"
    return "other"
