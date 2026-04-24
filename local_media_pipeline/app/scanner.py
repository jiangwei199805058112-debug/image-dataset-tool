from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from app.constants import FILE_STATUSES
from app.hashing import file_uid, quick_hash_md5
from app.metadata import detect_file_type

ProgressCallback = Callable[[str], None]
DOWNLOAD_TEMP_SUFFIXES = {
    ".tmp",
    ".downloading",
    ".crdownload",
    ".part",
    ".baiduyun",
    ".aria2",
    ".td",
    ".cfg",
}


@dataclass
class ScanResult:
    scanned_files: int = 0
    new_files: int = 0
    updated_files: int = 0
    skipped_files: int = 0
    error_files: int = 0


class InboxScanner:
    def __init__(self, db, inbox_root: Path, quick_hash_bytes: int = 65536):
        self.db = db
        self.inbox_root = inbox_root
        self.quick_hash_bytes = quick_hash_bytes
        self.logger = logging.getLogger("local_media_pipeline")
        assert "SURVEYED" in FILE_STATUSES

    def run_scan(self, progress: ProgressCallback | None = None) -> ScanResult:
        def emit(msg: str) -> None:
            if progress:
                progress(msg)

        result = ScanResult()
        if not self.inbox_root.exists() or not self.inbox_root.is_dir():
            message = f"INBOX 路径不存在：{self.inbox_root}"
            emit(message)
            self.logger.error(message)
            try:
                self.db.insert_log("ERROR", "scanner", message, target_type="path", target_id=str(self.inbox_root))
            except Exception:
                pass
            return result

        started_at = int(time.time())
        session_id = self._create_scan_session(started_at)
        emit(f"开始扫描：{self.inbox_root}")

        for root, _, files in os.walk(self.inbox_root):
            root_path = Path(root)
            for name in files:
                result.scanned_files += 1
                path = root_path / name
                lower_name = name.lower()

                if any(lower_name.endswith(suffix) for suffix in DOWNLOAD_TEMP_SUFFIXES):
                    result.skipped_files += 1
                    continue

                try:
                    stat = path.stat()
                    size = int(stat.st_size)
                    if size <= 0:
                        result.skipped_files += 1
                        continue

                    mtime = int(stat.st_mtime)
                    ctime = int(stat.st_ctime)
                    current_path = str(path.resolve())
                    existing = self.db.execute(
                        "SELECT id, file_size, mtime FROM files WHERE current_path=?",
                        (current_path,),
                    ).fetchone()
                    if existing and int(existing["file_size"] or 0) == size and int(existing["mtime"] or 0) == mtime:
                        result.skipped_files += 1
                        continue

                    quick_hash = quick_hash_md5(path, self.quick_hash_bytes)
                    ext = path.suffix.lower()
                    ftype = detect_file_type(path)
                    rel = str(path.resolve().relative_to(self.inbox_root.resolve()))
                    uid = file_uid(path, size, mtime)
                    now = int(time.time())

                    if existing:
                        self.db.execute(
                            """
                            UPDATE files SET
                              file_uid=?, original_path=?, relative_path=?, file_name=?, file_ext=?, file_type=?,
                              file_size=?, mtime=?, ctime=?, quick_hash=?, status=?, updated_at=?, error_message=NULL
                            WHERE id=?
                            """,
                            (
                                uid,
                                current_path,
                                rel,
                                path.name,
                                ext,
                                ftype,
                                size,
                                mtime,
                                ctime,
                                quick_hash,
                                "SURVEYED",
                                now,
                                int(existing["id"]),
                            ),
                        )
                        result.updated_files += 1
                        emit(f"更新：{current_path}")
                    else:
                        self.db.execute(
                            """
                            INSERT INTO files(
                              file_uid, original_path, current_path, relative_path, file_name, file_ext, file_type,
                              file_size, mtime, ctime, quick_hash, status, created_at, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                uid,
                                current_path,
                                current_path,
                                rel,
                                path.name,
                                ext,
                                ftype,
                                size,
                                mtime,
                                ctime,
                                quick_hash,
                                "SURVEYED",
                                now,
                                now,
                            ),
                        )
                        result.new_files += 1
                        emit(f"新增：{current_path}")
                    self.db.commit()
                except Exception as exc:
                    result.error_files += 1
                    message = f"扫描文件失败：{path}，错误：{exc}"
                    emit(message)
                    self.logger.exception(message)
                    try:
                        self.db.insert_log("ERROR", "scanner", message, target_type="file", target_id=str(path))
                    except Exception:
                        pass

        self._finish_scan_session(session_id, result, int(time.time()))
        emit(
            f"扫描完成，总计={result.scanned_files}, 新增={result.new_files}, 更新={result.updated_files},"
            f" 跳过={result.skipped_files}, 错误={result.error_files}"
        )
        return result

    def _create_scan_session(self, started_at: int) -> int:
        cur = self.db.execute(
            "INSERT INTO scan_sessions(root_path, status, started_at) VALUES (?, ?, ?)",
            (str(self.inbox_root), "RUNNING", started_at),
        )
        self.db.commit()
        return int(cur.lastrowid)

    def _finish_scan_session(self, session_id: int, result: ScanResult, finished_at: int) -> None:
        self.db.execute(
            """
            UPDATE scan_sessions
            SET status=?, scanned_files=?, new_files=?, updated_files=?, finished_at=?
            WHERE id=?
            """,
            ("DONE", result.scanned_files, result.new_files, result.updated_files, finished_at, session_id),
        )
        self.db.commit()
