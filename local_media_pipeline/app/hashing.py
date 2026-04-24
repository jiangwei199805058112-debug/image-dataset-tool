from __future__ import annotations

import hashlib
from pathlib import Path


def quick_hash_md5(path: Path, bytes_to_read: int = 65536) -> str:
    md5 = hashlib.md5()
    with path.open("rb") as f:
        md5.update(f.read(bytes_to_read))
    return md5.hexdigest()


def file_uid(path: Path, file_size: int, mtime: int) -> str:
    src = f"{path.resolve()}|{file_size}|{mtime}".encode("utf-8", errors="ignore")
    return hashlib.sha1(src).hexdigest()
