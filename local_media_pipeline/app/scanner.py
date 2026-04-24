from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Callable

from app.constants import FILE_STATUSES
from app.hashing import file_uid, quick_hash_md5
from app.metadata import KNOWN_EXT_TYPE, classify_file_type

ProgressCallback = Callable[[dict], None]
DOWNLOAD_TEMP_SUFFIXES = {".tmp", ".downloading", ".crdownload", ".part", ".baiduyun", ".aria2", ".td", ".cfg"}
SYSTEM_SKIP_DIRS = {"$RECYCLE.BIN", "System Volume Information", "_VAULT_", "_ARCHIVE_", "DATA_PIPELINE"}


@dataclass
class ScanResult:
    scanned_files: int = 0
    new_files: int = 0
    updated_files: int = 0
    skipped_files: int = 0
    error_files: int = 0


class InboxScanner:
    def __init__(self, db, inbox_root: Path, quick_hash_bytes: int = 65536, exclude_roots: list[Path] | None = None, summary_every: int = 500):
        self.db = db
        self.inbox_root = inbox_root
        self.quick_hash_bytes = quick_hash_bytes
        self.exclude_roots = [p.resolve() for p in (exclude_roots or []) if str(p)]
        self.summary_every = max(100, summary_every)
        self.logger = logging.getLogger("local_media_pipeline")
        self.pause_requested = Event()
        self.stop_requested = Event()
        assert "SURVEYED" in FILE_STATUSES

    def pause(self) -> None:
        self.pause_requested.set()

    def resume(self) -> None:
        self.pause_requested.clear()

    def stop(self) -> None:
        self.stop_requested.set()

    def run_scan(self, progress: ProgressCallback | None = None) -> ScanResult:
        def emit(payload: dict) -> None:
            if progress:
                progress(payload)

        result = ScanResult()
        current_path = ""

        if not self.inbox_root.exists() or not self.inbox_root.is_dir():
            msg = f"INBOX 路径不存在：{self.inbox_root}"
            self.logger.error(msg)
            self.db.insert_log("ERROR", "scanner", msg, "path", str(self.inbox_root))
            emit(self._progress_dict(result, current_path, msg))
            return result

        latest = self.db.get_latest_scan_session(str(self.inbox_root))
        resume_note = ""
        if latest and str(latest["status"] or "") in {"PAUSED", "STOPPED"}:
            resume_note = "检测到未完成扫描，正在从上次位置继续..."
            emit(self._progress_dict(result, current_path, resume_note))

        session_id = self.db.create_scan_session(str(self.inbox_root), note=resume_note)
        emit(self._progress_dict(result, current_path, f"开始扫描：{self.inbox_root}"))

        try:
            for root, dirs, files in os.walk(self.inbox_root, topdown=True):
                root_path = Path(root).resolve()
                current_path = str(root_path)
                if self._handle_pause_stop(session_id, current_path, result, emit):
                    return result

                if self._is_excluded_root(root_path):
                    dirs[:] = []
                    continue
                dirs[:] = [d for d in dirs if not self._is_excluded_dir(root_path / d)]

                for name in files:
                    if self._handle_pause_stop(session_id, current_path, result, emit):
                        return result

                    result.scanned_files += 1
                    path = root_path / name
                    current_path = str(path)

                    lower_name = name.lower()
                    if any(lower_name.endswith(s) for s in DOWNLOAD_TEMP_SUFFIXES):
                        result.skipped_files += 1
                        continue

                    try:
                        st = path.stat()
                        size = int(st.st_size)
                        if size <= 0:
                            result.skipped_files += 1
                            continue

                        mtime = int(st.st_mtime)
                        ctime = int(st.st_ctime)
                        abs_path = str(path.resolve())

                        existing = self.db.execute("SELECT id,file_size,mtime FROM files WHERE current_path=?", (abs_path,)).fetchone()
                        if existing and int(existing["file_size"] or 0) == size and int(existing["mtime"] or 0) == mtime:
                            result.skipped_files += 1
                            continue

                        ext = path.suffix.lower()
                        confirmed = self.db.get_confirmed_type(ext) if ext else None
                        ftype = classify_file_type(ext, confirmed)
                        quick_hash = quick_hash_md5(path, self.quick_hash_bytes)
                        rel = str(path.resolve().relative_to(self.inbox_root.resolve()))
                        uid = file_uid(path, size, mtime)
                        now = int(time.time())

                        if existing:
                            self.db.execute(
                                "UPDATE files SET file_uid=?,original_path=?,relative_path=?,file_name=?,file_ext=?,file_type=?,file_size=?,mtime=?,ctime=?,quick_hash=?,status=?,updated_at=?,error_message=NULL WHERE id=?",
                                (uid, abs_path, rel, path.name, ext, ftype, size, mtime, ctime, quick_hash, "SURVEYED", now, int(existing["id"])),
                            )
                            result.updated_files += 1
                        else:
                            self.db.execute(
                                "INSERT INTO files(file_uid,original_path,current_path,relative_path,file_name,file_ext,file_type,file_size,mtime,ctime,quick_hash,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                                (uid, abs_path, abs_path, rel, path.name, ext, ftype, size, mtime, ctime, quick_hash, "SURVEYED", now, now),
                            )
                            result.new_files += 1

                        if ext:
                            self.db.upsert_extension_stat(ext, guessed_type=(KNOWN_EXT_TYPE.get(ext, "other")), is_known=1 if ext in KNOWN_EXT_TYPE else 0)
                        self.db.commit()
                    except Exception as exc:
                        result.error_files += 1
                        msg = f"扫描文件失败：{path}，错误：{exc}"
                        self.logger.exception(msg)
                        self.db.insert_log("ERROR", "scanner", msg, "file", str(path))

                    if result.scanned_files % self.summary_every == 0:
                        self.db.update_scan_session(session_id, "RUNNING", current_path, result.scanned_files, result.new_files, result.updated_files, result.skipped_files, result.error_files)
                        emit(self._progress_dict(result, current_path, ""))

            self.db.finish_scan_session(session_id, "FINISHED", note="扫描完成")
            final_msg = f"扫描完成：总计={result.scanned_files}，新增={result.new_files}，更新={result.updated_files}，跳过={result.skipped_files}，错误={result.error_files}。"
            self.db.insert_log("INFO", "scanner", final_msg)
            emit(self._progress_dict(result, current_path, final_msg))
            return result
        except Exception as exc:
            self.db.finish_scan_session(session_id, "FAILED", note=str(exc))
            err = f"扫描任务失败：{exc}"
            self.db.insert_log("ERROR", "scanner", err)
            emit(self._progress_dict(result, current_path, err))
            return result

    def _progress_dict(self, result: ScanResult, current_path: str, message: str) -> dict:
        stats = self.db.get_dashboard_stats()
        return {
            "scanned_files": result.scanned_files,
            "new_files": result.new_files,
            "updated_files": result.updated_files,
            "skipped_files": result.skipped_files,
            "error_files": result.error_files,
            "current_path": current_path,
            "type_counts": {
                "image": stats["image_count"],
                "raw_image": stats["raw_image_count"],
                "video": stats["video_count"],
                "document": stats["document_count"],
                "archive": stats["archive_count"],
                "software": stats["software_count"],
                "audio": stats["audio_count"],
                "other": stats["other_count"],
            },
            "message": message,
        }

    def _handle_pause_stop(self, session_id: int, current_path: str, result: ScanResult, emit: ProgressCallback) -> bool:
        if self.stop_requested.is_set():
            self.db.update_scan_session(session_id, "STOPPED", current_path, result.scanned_files, result.new_files, result.updated_files, result.skipped_files, result.error_files, note="用户停止")
            msg = "扫描已停止，进度已保存，可稍后继续。"
            self.db.insert_log("INFO", "scanner", msg)
            emit(self._progress_dict(result, current_path, msg))
            return True

        while self.pause_requested.is_set():
            self.db.update_scan_session(session_id, "PAUSED", current_path, result.scanned_files, result.new_files, result.updated_files, result.skipped_files, result.error_files, note="用户暂停")
            msg = "扫描已暂停，进度已保存。"
            self.db.insert_log("INFO", "scanner", msg)
            emit(self._progress_dict(result, current_path, msg))
            while self.pause_requested.is_set() and not self.stop_requested.is_set():
                time.sleep(0.2)
            if self.stop_requested.is_set():
                return self._handle_pause_stop(session_id, current_path, result, emit)
            self.db.update_scan_session(session_id, "RUNNING", current_path, result.scanned_files, result.new_files, result.updated_files, result.skipped_files, result.error_files, note="继续")
            emit(self._progress_dict(result, current_path, "继续扫描 INBOX..."))
        return False

    def _is_excluded_root(self, path: Path) -> bool:
        for ex in self.exclude_roots:
            try:
                if path == ex or ex in path.parents:
                    return True
            except Exception:
                continue
        return any(name in SYSTEM_SKIP_DIRS or name.startswith(".") for name in path.parts)

    def _is_excluded_dir(self, path: Path) -> bool:
        return self._is_excluded_root(path.resolve())
