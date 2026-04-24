from __future__ import annotations

from pathlib import Path
from typing import Callable

from app.config import load_config, save_config
from app.db import Database
from app.logger import setup_logger
from app.paths import AppPaths, build_paths, init_pipeline_directories
from app.scanner import InboxScanner, ScanResult


class AppServices:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.config = load_config(project_root)
        self.paths: AppPaths = build_paths(self.config)
        self.logger = setup_logger(self.paths.log_path) if self.paths.pipeline_root else setup_logger(project_root / "pipeline.log")
        self.db = Database(self.paths.database_path)

    def has_required_paths(self) -> bool:
        return bool(self.config.get("inbox_path") and self.config.get("vault_path") and self.config.get("pipeline_root"))

    def reload_config(self) -> None:
        self.config = load_config(self.project_root)
        self.paths = build_paths(self.config)
        self.logger = setup_logger(self.paths.log_path) if self.paths.pipeline_root else setup_logger(self.project_root / "pipeline.log")
        self.db = Database(self.paths.database_path)

    def save_paths_config(self, inbox_path: str, vault_path: str, pipeline_root: str) -> tuple[bool, str]:
        try:
            payload = {
                "inbox_path": inbox_path,
                "vault_path": vault_path,
                "pipeline_root": pipeline_root,
            }
            save_config(self.project_root, payload)
            self.reload_config()

            for p in [self.paths.inbox_path, self.paths.vault_path]:
                p.mkdir(parents=True, exist_ok=True)

            ok, message = init_pipeline_directories(self.paths)
            if not ok:
                return False, message

            return True, "路径设置保存成功"
        except Exception as exc:
            self.safe_log_db("ERROR", "services", f"保存路径配置失败：{exc}")
            return False, f"保存路径配置失败：{exc}"

    def initialize_database(self) -> tuple[bool, str]:
        if not self.has_required_paths():
            return False, "请先在设置中配置 INBOX/VAULT/PIPELINE_ROOT 路径。"
        try:
            ok, message = init_pipeline_directories(self.paths)
            if not ok:
                return False, message
            self.db.connect()
            self.db.init_schema()
            self.logger.info("数据库初始化完成")
            self.safe_log_db("INFO", "services", "数据库初始化完成")
            return True, "数据库初始化成功"
        except Exception as exc:
            err = f"数据库初始化失败：{exc}"
            self.logger.exception(err)
            self.safe_log_db("ERROR", "services", err)
            return False, err

    def scan_inbox(self, progress: Callable[[str], None] | None = None) -> ScanResult:
        if not self.has_required_paths():
            raise ValueError("请先设置路径后再扫描。")
        scanner = InboxScanner(
            db=self.db,
            inbox_root=self.paths.inbox_path,
            quick_hash_bytes=65536,
        )
        return scanner.run_scan(progress=progress)

    def safe_log_db(self, level: str, module: str, message: str) -> None:
        try:
            if self.db.conn is None and self.paths.pipeline_root:
                self.db.connect()
                self.db.init_schema()
            if self.db.conn is not None:
                self.db.insert_log(level, module, message)
        except Exception:
            self.logger.warning(message)
