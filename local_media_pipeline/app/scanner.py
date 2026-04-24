from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from app.constants import FILE_STATUSES
from app.hashing import file_uid, quick_hash_md5
from app.metadata import KNOWN_EXT_TYPE, classify_file_type

ProgressCallback = Callable[[str], None]
DOWNLOAD_TEMP_SUFFIXES = {".tmp", ".downloading", ".crdownload", ".part", ".baiduyun", ".aria2", ".td", ".cfg"}
SYSTEM_SKIP_DIRS = {"$RECYCLE.BIN", "System Volume Information", "_VAULT_", "_ARCHIVE_", "DATA_PIPELINE"}


@dataclass
class ScanResult:
    scanned_files: int = 0
    new_files: int = 0
    updated_files: int = 0
    skipped_files: int = 0
    error_files: int = 0


class ScanControl:
    def __init__(self):
        self.pause_event = threading.Event()
        self.stop_event = threading.Event()

    def request_pause(self) -> None:
        self.pause_event.set()

    def request_resume(self) -> None:
        self.pause_event.clear()

    def request_stop(self) -> None:
        self.stop_event.set()


class InboxScanner:
    def __init__(self, db, inbox_root: Path, quick_hash_bytes: int = 65536, exclude_roots: list[Path] | None = None, control: ScanControl | None = None, summary_every: int = 500):
        self.db = db
        self.inbox_root = inbox_root
        self.quick_hash_bytes = quick_hash_bytes
        self.exclude_roots = [p.resolve() for p in (exclude_roots or []) if str(p)]
        self.control = control or ScanControl()
        self.summary_every = summary_every
        self.logger = logging.getLogger("local_media_pipeline")
        assert "SURVEYED" in FILE_STATUSES

    def run_scan(self, progress: ProgressCallback | None = None) -> ScanResult:
        def emit(msg: str) -> None:
            if progress:
                progress(msg)

        result = ScanResult()
        if not self.inbox_root.exists() or not self.inbox_root.is_dir():
            msg = f"INBOX 路径不存在：{self.inbox_root}"
            self.logger.error(msg)
            emit(msg)
            self.db.insert_log("ERROR", "scanner", msg, "path", str(self.inbox_root))
            return result

        resume_note = ""
        latest = self.db.get_latest_scan_session(str(self.inbox_root))
        if latest and str(latest["status"] or "") in {"PAUSED", "STOPPED"}:
            resume_note = "检测到未完成扫描，正在从上次位置继续..."
            emit(resume_note)

        session_id = self.db.create_scan_session(str(self.inbox_root), note=resume_note)
        emit(f"开始扫描：{self.inbox_root}")

        last_path: str | None = None
        try:
            for root, dirs, files in os.walk(self.inbox_root, topdown=True):
                root_path = Path(root).resolve()
                if self._check_pause_stop(session_id, last_path, result, emit):
                    return result

                if self._is_excluded_root(root_path):
                    dirs[:] = []
                    continue
                dirs[:] = [d for d in dirs if not self._is_excluded_dir(root_path / d)]

                for name in files:
                    if self._check_pause_stop(session_id, last_path, result, emit):
                        return result
                    result.scanned_files += 1
                    path = root_path / name
                    last_path = str(path)
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
                        current_path = str(path.resolve())
                        existing = self.db.execute("SELECT id,file_size,mtime FROM files WHERE current_path=?", (current_path,)).fetchone()
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
                                (uid, current_path, rel, path.name, ext, ftype, size, mtime, ctime, quick_hash, "SURVEYED", now, int(existing["id"])),
                            )
                            result.updated_files += 1
                        else:
                            self.db.execute(
                                "INSERT INTO files(file_uid,original_path,current_path,relative_path,file_name,file_ext,file_type,file_size,mtime,ctime,quick_hash,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                                (uid, current_path, current_path, rel, path.name, ext, ftype, size, mtime, ctime, quick_hash, "SURVEYED", now, now),
                            )
                            result.new_files += 1

                        if ext:
                            self.db.upsert_extension_stat(ext, guessed_type=(KNOWN_EXT_TYPE.get(ext, "other")), is_known=1 if ext in KNOWN_EXT_TYPE else 0)

                        self.db.commit()
                    except Exception as exc:
                        result.error_files += 1
                        msg = f"扫描文件失败：{path}，错误：{exc}"
                        self.logger.exception(msg)
                        emit(msg)
                        self.db.insert_log("ERROR", "scanner", msg, "file", str(path))

                    if result.scanned_files % self.summary_every == 0:
                        emit(self._summary_text(result))
                        self._emit_unknown_extensions(emit)
                        self.db.update_scan_session(session_id, "RUNNING", last_path, result.scanned_files, result.new_files, result.updated_files, result.skipped_files, result.error_files)

            self.db.finish_scan_session(session_id, "FINISHED", note="扫描完成")
            msg = f"扫描完成：总计={result.scanned_files}，新增={result.new_files}，更新={result.updated_files}，跳过={result.skipped_files}，错误={result.error_files}。"
            emit(msg)
            self.db.insert_log("INFO", "scanner", msg)
            self._emit_unknown_extensions(emit)
            return result
        except Exception as exc:
            self.db.finish_scan_session(session_id, "FAILED", note=str(exc))
            self.db.insert_log("ERROR", "scanner", f"扫描任务失败：{exc}")
            emit(f"扫描失败：{exc}")
            return result

    def _check_pause_stop(self, session_id: int, last_path: str | None, result: ScanResult, emit: ProgressCallback) -> bool:
        if self.control.stop_event.is_set():
            self.db.update_scan_session(session_id, "STOPPED", last_path, result.scanned_files, result.new_files, result.updated_files, result.skipped_files, result.error_files, note="用户停止")
            msg = "扫描已停止，进度已保存，可稍后继续。"
            self.db.insert_log("INFO", "scanner", msg)
            emit(msg)
            return True

        while self.control.pause_event.is_set():
            self.db.update_scan_session(session_id, "PAUSED", last_path, result.scanned_files, result.new_files, result.updated_files, result.skipped_files, result.error_files, note="用户暂停")
            msg = "扫描已暂停，进度已保存。"
            self.db.insert_log("INFO", "scanner", msg)
            emit(msg)
            while self.control.pause_event.is_set() and not self.control.stop_event.is_set():
                time.sleep(0.2)
            if self.control.stop_event.is_set():
                return self._check_pause_stop(session_id, last_path, result, emit)
            self.db.update_scan_session(session_id, "RUNNING", last_path, result.scanned_files, result.new_files, result.updated_files, result.skipped_files, result.error_files, note="继续")
            emit("继续扫描 INBOX...")
            self.db.insert_log("INFO", "scanner", "继续扫描 INBOX...")
        return False

    def _summary_text(self, result: ScanResult) -> str:
        s = self.db.get_dashboard_stats()
        return (
            f"已扫描：{result.scanned_files}\n新增：{result.new_files}\n更新：{result.updated_files}\n跳过：{result.skipped_files}\n错误：{result.error_files}\n"
            f"图片：{s['image_count']}\nRAW：{s['raw_image_count']}\n视频：{s['video_count']}\n文档：{s['document_count']}\n"
            f"压缩包：{s['archive_count']}\n软件：{s['software_count']}\n音频：{s['audio_count']}\n其他：{s['other_count']}"
        )

    def _emit_unknown_extensions(self, emit: ProgressCallback) -> None:
        rows = self.db.get_unknown_extensions(10)
        for row in rows:
            ext = str(row["ext"])
            cnt = int(row["detected_count"] or 0)
            if ext.startswith(".ar") or ext.startswith(".cr") or ext.startswith(".ne"):
                emit(f"发现未知扩展名 {ext} 共 {cnt} 个，可能是相机 RAW 或素材文件，请确认分类。")
            else:
                emit(f"发现大量未知扩展名：{ext}，共 {cnt} 个，请确认分类。")

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
