from __future__ import annotations

import hashlib
from pathlib import Path


def quick_hash_md5(path: Path, bytes_to_read: int = 65536) -> str:
    """读取文件前 64KB（默认）计算 quick hash。"""
    md5 = hashlib.md5()
    with path.open("rb") as f:
        md5.update(f.read(bytes_to_read))
    return md5.hexdigest()


def full_hash_sha256_chunked(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """完整 hash（分块读取），仅建议在 SSD 批处理阶段使用。"""
    sha = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            sha.update(chunk)
    return sha.hexdigest()


def file_uid(path: Path, file_size: int, mtime: int) -> str:
    src = f"{path.resolve()}|{file_size}|{mtime}".encode("utf-8", errors="ignore")
    return hashlib.sha1(src).hexdigest()
