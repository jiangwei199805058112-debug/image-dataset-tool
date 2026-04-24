from __future__ import annotations

import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from app.file_ops import new_batch_id, safe_copy_file, safe_move_file


@dataclass
class BatchExtractResult:
    success: bool
    batch_id: str
    total_files: int
    moved_files: int
    failed_files: int
    message: str


class BatchService:
    def __init__(self, db, paths, config: dict):
        self.db = db
        self.paths = paths
        self.config = config

    def extract_to_processing(self, progress: Callable[[str], None] | None = None) -> BatchExtractResult:
        def emit(msg: str) -> None:
            if progress:
                progress(msg)
            try:
                self.db.insert_log("INFO", "batch", msg)
            except Exception:
                pass

        try:
            total, used, free = shutil.disk_usage(self.paths.pipeline_root)
            free_limit = int(free * 0.6)
            batch_limit = int(float(self.config.get("batch_size_gb", 100)) * 1024 * 1024 * 1024)
            effective_limit = min(batch_limit, free_limit)
            if effective_limit <= 0:
                return BatchExtractResult(False, "", 0, 0, 0, "SSD 可用空间不足，请减小批次大小或清理工作区。")

            candidates = self.db.fetch_candidate_batch_files(effective_limit)
            if not candidates:
                return BatchExtractResult(False, "", 0, 0, 0, "没有可提取的 SURVEYED 文件。")

            selected_size = sum(int(r["file_size"] or 0) for r in candidates)
            if selected_size > free_limit:
                return BatchExtractResult(False, "", 0, 0, 0, "SSD 可用空间不足，请减小批次大小或清理工作区。")

            batch_id = new_batch_id()
            batch_dir = self.paths.processing_dir / batch_id
            batch_dir.mkdir(parents=True, exist_ok=True)
            self.db.create_batch(batch_id, batch_id, str(batch_dir), len(candidates), selected_size)

            single_copy_mode = bool(self.config.get("single_copy_mode", False))
            moved = 0
            failed = 0
            for row in candidates:
                file_id = int(row["id"])
                src = Path(str(row["current_path"]))
                dst = batch_dir / str(row["file_name"])
                job_id = self.db.create_archive_job(
                    batch_id=batch_id,
                    target_type="file",
                    target_id=str(file_id),
                    source_path=str(src),
                    temp_path=str(self.paths.temp_dir),
                    final_path=str(dst),
                )
                emit(f"处理文件：{src}")
                self.db.update_archive_job(job_id, "COPYING")
                if single_copy_mode:
                    result = safe_move_file(src, dst, self.paths.temp_dir, db=self.db)
                else:
                    result = safe_copy_file(src, dst, self.paths.temp_dir, db=self.db)

                if result.success:
                    self.db.update_archive_job(job_id, "VERIFYING", source_hash=result.source_hash, target_hash=result.target_hash, bytes_copied=result.bytes_copied)
                    self.db.update_archive_job(job_id, "COMMITTED")
                    self.db.update_archive_job(job_id, "CLEANED")
                    self.db.mark_file_staged(file_id, str(dst), batch_id)
                    moved += 1
                else:
                    self.db.update_archive_job(
                        job_id,
                        "FAILED",
                        source_hash=result.source_hash,
                        target_hash=result.target_hash,
                        bytes_copied=result.bytes_copied,
                        error_message=result.error_message,
                    )
                    self.db.mark_file_error(file_id, result.error_message)
                    self.db.insert_log("ERROR", "batch", f"文件提取失败：{src}，原因：{result.error_message}", "file", str(file_id))
                    failed += 1

            status = "DONE" if failed == 0 else "FAILED"
            self.db.finish_batch(batch_id, status, f"moved={moved}, failed={failed}, mode={'single' if single_copy_mode else 'copy'}")
            return BatchExtractResult(True, batch_id, len(candidates), moved, failed, f"批次提取完成：成功 {moved}，失败 {failed}")
        except Exception as exc:
            self.db.insert_log("ERROR", "batch", f"批次提取异常：{exc}")
            return BatchExtractResult(False, "", 0, 0, 0, f"批次提取失败：{exc}")
