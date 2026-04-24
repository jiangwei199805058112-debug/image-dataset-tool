from __future__ import annotations

from pathlib import Path

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".webp", ".gif", ".bmp", ".tif", ".tiff"}
RAW_IMAGE_EXTS = {".arw", ".raw", ".cr2", ".cr3", ".nef", ".raf", ".dng", ".orf", ".rw2", ".srw", ".pef", ".x3f"}
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".mts", ".m2ts", ".wmv", ".flv", ".webm", ".3gp"}
DOCUMENT_EXTS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".hwp", ".md", ".csv"}
ARCHIVE_EXTS = {".zip", ".rar", ".7z", ".tar", ".gz", ".iso"}
SOFTWARE_EXTS = {".exe", ".msi", ".dll", ".sys", ".bat", ".cmd", ".apk", ".pkg", ".dmg"}
AUDIO_EXTS = {".mp3", ".wav", ".flac", ".aac", ".m4a", ".ogg", ".wma"}

KNOWN_EXT_TYPE: dict[str, str] = {}
for e in IMAGE_EXTS:
    KNOWN_EXT_TYPE[e] = "image"
for e in RAW_IMAGE_EXTS:
    KNOWN_EXT_TYPE[e] = "raw_image"
for e in VIDEO_EXTS:
    KNOWN_EXT_TYPE[e] = "video"
for e in DOCUMENT_EXTS:
    KNOWN_EXT_TYPE[e] = "document"
for e in ARCHIVE_EXTS:
    KNOWN_EXT_TYPE[e] = "archive"
for e in SOFTWARE_EXTS:
    KNOWN_EXT_TYPE[e] = "software"
for e in AUDIO_EXTS:
    KNOWN_EXT_TYPE[e] = "audio"


def classify_file_type(ext: str, confirmed_type: str | None = None) -> str:
    if confirmed_type:
        return confirmed_type
    return KNOWN_EXT_TYPE.get(ext.lower(), "other")


def detect_file_type(path: Path, confirmed_type: str | None = None) -> str:
    return classify_file_type(path.suffix.lower(), confirmed_type)
