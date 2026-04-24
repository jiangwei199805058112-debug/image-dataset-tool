from __future__ import annotations

import hashlib
import os
import shutil
import time
import uuid
from dataclasses import dataclass
from pathlib import Path


@dataclass
class SafeMoveResult:
    success: bool
    source_hash: str | None = None
    target_hash: str | None = None
    temp_path: Path | None = None
    final_path: Path | None = None
    bytes_copied: int = 0
    error_message: str = ""


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def safe_move_file(src: Path, dst_final: Path, tmp_dir: Path, expected_hash: str | None = None, db=None) -> SafeMoveResult:
    return _safe_transfer_file(src, dst_final, tmp_dir, expected_hash=expected_hash, delete_source=True, db=db)


def safe_copy_file(src: Path, dst_final: Path, tmp_dir: Path, expected_hash: str | None = None, db=None) -> SafeMoveResult:
    return _safe_transfer_file(src, dst_final, tmp_dir, expected_hash=expected_hash, delete_source=False, db=db)


def _safe_transfer_file(
    src: Path,
    dst_final: Path,
    tmp_dir: Path,
    expected_hash: str | None,
    delete_source: bool,
    db,
) -> SafeMoveResult:
    temp_path: Path | None = None
    try:
        src = src.resolve()
        tmp_dir.mkdir(parents=True, exist_ok=True)
        temp_path = tmp_dir / f"{src.name}.{uuid.uuid4().hex}.tmp"

        _db_log(db, "INFO", "file_ops", f"开始复制到临时文件：{src} -> {temp_path}")
        shutil.copy2(src, temp_path)
        bytes_copied = int(temp_path.stat().st_size)

        _db_log(db, "INFO", "file_ops", f"开始校验：{src}")
        src_hash = sha256_file(src)
        tmp_hash = sha256_file(temp_path)
        reference_hash = expected_hash or src_hash
        if tmp_hash != reference_hash:
            temp_path.unlink(missing_ok=True)
            return SafeMoveResult(
                success=False,
                source_hash=src_hash,
                target_hash=tmp_hash,
                temp_path=temp_path,
                final_path=dst_final,
                bytes_copied=bytes_copied,
                error_message="Hash 校验失败，已保留源文件。",
            )

        dst_final.parent.mkdir(parents=True, exist_ok=True)
        _db_log(db, "INFO", "file_ops", f"提交最终文件：{temp_path} -> {dst_final}")
        shutil.copy2(temp_path, dst_final)
        final_hash = sha256_file(dst_final)
        if final_hash != reference_hash:
            dst_final.unlink(missing_ok=True)
            temp_path.unlink(missing_ok=True)
            return SafeMoveResult(
                success=False,
                source_hash=src_hash,
                target_hash=final_hash,
                temp_path=temp_path,
                final_path=dst_final,
                bytes_copied=bytes_copied,
                error_message="最终文件校验失败，已保留源文件。",
            )

        temp_path.unlink(missing_ok=True)
        if delete_source:
            os.remove(src)
        return SafeMoveResult(
            success=True,
            source_hash=src_hash,
            target_hash=final_hash,
            temp_path=temp_path,
            final_path=dst_final,
            bytes_copied=bytes_copied,
        )
    except Exception as exc:
        try:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
        except Exception:
            pass
        _db_log(db, "ERROR", "file_ops", f"安全移动失败：{exc}")
        return SafeMoveResult(success=False, temp_path=temp_path, final_path=dst_final, error_message=f"安全移动失败：{exc}")


def _db_log(db, level: str, module: str, message: str) -> None:
    if db is None:
        return
    try:
        db.insert_log(level, module, message)
    except Exception:
        pass


def new_batch_id() -> str:
    return f"BATCH_{int(time.time())}_{uuid.uuid4().hex[:8]}"
