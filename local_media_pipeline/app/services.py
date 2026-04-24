from __future__ import annotations

from pathlib import Path
from typing import Callable

from app.config import load_config
from app.db import Database
from app.logger import setup_logger
from app.paths import AppPaths, build_paths, init_directories
from app.scanner import InboxScanner, ScanResult


class AppServices:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.config = load_config(project_root)
        self.paths: AppPaths = build_paths(self.config)
        self.logger = setup_logger(self.paths.log_path)
        self.db = Database(self.paths.database_path)

    def initialize_database(self) -> tuple[bool, str]:
        ok, message = init_directories(self.paths)
        if not ok:
            return False, message
        try:
            self.db.connect()
            self.db.init_schema()
            self.logger.info("数据库初始化完成")
            self.db.insert_log("INFO", "services", "数据库初始化完成")
            return True, "数据库初始化成功"
        except Exception as exc:
            err = f"数据库初始化失败：{exc}"
            self.logger.exception(err)
            return False, err

    def scan_inbox(self, progress: Callable[[str], None] | None = None) -> ScanResult:
        scanner = InboxScanner(
            db=self.db,
            inbox_root=self.paths.inbox_root,
            quick_hash_bytes=int(self.config["scanner"].get("quick_hash_bytes", 65536)),
        )
        return scanner.run_scan(progress=progress)
