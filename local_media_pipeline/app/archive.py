from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from app.file_ops import safe_move_file


@dataclass
class ArchiveResult:
    success: bool
    archived_files: int
    failed_files: int
    message: str


class ArchiveService:
    def __init__(self, db, paths):
        self.db = db
        self.paths = paths

    def archive_ready_files(self, progress: Callable[[str], None] | None = None) -> ArchiveResult:
        def emit(msg: str) -> None:
            if progress:
                progress(msg)
            try:
                self.db.insert_log("INFO", "archive", msg)
            except Exception:
                pass

        try:
            rows = self.db.fetch_ready_to_archive_files()
            if not rows:
                return ArchiveResult(False, 0, 0, "没有 READY_TO_ARCHIVE 文件。")

            archived = 0
            failed = 0
            for row in rows:
                file_id = int(row["id"])
                src = Path(str(row["current_path"]))
                category = str(row["category"] or "uncategorized")
                event_id = str(row["event_id"] or f"event_{file_id}")
                mtime = int(row["mtime"] or 0)
                year = datetime.fromtimestamp(mtime).strftime("%Y") if mtime > 0 else "unknown_year"
                dst = self.paths.vault_path / category / year / event_id / str(row["file_name"])

                job_id = self.db.create_archive_job(
                    batch_id=None,
                    target_type="file",
                    target_id=str(file_id),
                    source_path=str(src),
                    temp_path=str(self.paths.temp_dir),
                    final_path=str(dst),
                )
                self.db.update_archive_job(job_id, "COPYING")
                result = safe_move_file(src, dst, self.paths.temp_dir, db=self.db)
                if result.success:
                    self.db.update_archive_job(job_id, "VERIFYING", source_hash=result.source_hash, target_hash=result.target_hash, bytes_copied=result.bytes_copied)
                    self.db.update_archive_job(job_id, "COMMITTED")
                    self.db.update_archive_job(job_id, "CLEANED")
                    self.db.mark_file_archived(file_id, str(dst))
                    archived += 1
                    emit(f"归档成功：{dst}")
                else:
                    self.db.update_archive_job(
                        job_id,
                        "FAILED",
                        source_hash=result.source_hash,
                        target_hash=result.target_hash,
                        bytes_copied=result.bytes_copied,
                        error_message=result.error_message,
                    )
                    self.db.mark_file_error(file_id, result.error_message, fallback_status="READY_TO_ARCHIVE")
                    self.db.insert_log("ERROR", "archive", f"归档失败：{src}，原因：{result.error_message}", "file", str(file_id))
                    failed += 1

            return ArchiveResult(True, archived, failed, f"归档完成：成功 {archived}，失败 {failed}")
        except Exception as exc:
            self.db.insert_log("ERROR", "archive", f"归档任务异常：{exc}")
            return ArchiveResult(False, 0, 0, f"归档失败：{exc}")
