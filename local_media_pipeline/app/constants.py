from __future__ import annotations

FILE_STATUSES = [
    "INBOX",
    "SURVEYED",
    "STAGED",
    "PROCESSING",
    "DUPLICATE",
    "AUTO_PASS",
    "REVIEW_PENDING",
    "REVIEWED",
    "READY_TO_ARCHIVE",
    "ARCHIVING",
    "ARCHIVED",
    "SNOOZED",
    "HARD_CASE",
    "TO_DELETE",
    "DELETED",
    "ERROR",
]

EVENT_STATUSES = [
    "NEW",
    "GROUPED",
    "AUTO_PASS",
    "REVIEW_PENDING",
    "REVIEWED",
    "READY_TO_ARCHIVE",
    "ARCHIVED",
    "SNOOZED",
    "HARD_CASE",
    "ERROR",
]

BATCH_STATUSES = [
    "CREATED",
    "STAGING",
    "PROCESSING",
    "ARBITRATING",
    "ARCHIVING",
    "DONE",
    "FAILED",
    "CANCELLED",
]

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".webp", ".gif"}
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".mts", ".m2ts", ".wmv"}
DOCUMENT_EXTS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt"}
ARCHIVE_EXTS = {".zip", ".rar", ".7z", ".tar", ".gz"}
