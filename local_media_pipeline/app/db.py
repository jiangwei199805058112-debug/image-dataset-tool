from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any

from app import schema


class Database:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn: sqlite3.Connection | None = None

    def connect(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._apply_pragmas()

    def _apply_pragmas(self) -> None:
        assert self.conn is not None
        for pragma in schema.PRAGMAS:
            self.conn.execute(pragma)
        self.conn.commit()

    def init_schema(self) -> None:
        assert self.conn is not None
        for sql in schema.TABLES_SQL:
            self.conn.execute(sql)
        for sql in schema.INDEXES_SQL:
            self.conn.execute(sql)
        self.conn.commit()

    def close(self) -> None:
        if self.conn is not None:
            self.conn.close()
            self.conn = None

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Cursor:
        assert self.conn is not None
        return self.conn.execute(sql, params)

    def commit(self) -> None:
        assert self.conn is not None
        self.conn.commit()

    def insert_log(
        self,
        level: str,
        module: str,
        message: str,
        target_type: str | None = None,
        target_id: str | None = None,
    ) -> None:
        now = int(time.time())
        self.execute(
            """
            INSERT INTO logs(level, module, target_type, target_id, message, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (level, module, target_type, target_id, message, now),
        )
        self.commit()

    def get_dashboard_stats(self) -> dict[str, int]:
        rows = self.execute(
            """
            SELECT
              COUNT(*) AS total,
              SUM(CASE WHEN file_type='image' THEN 1 ELSE 0 END) AS image_count,
              SUM(CASE WHEN file_type='video' THEN 1 ELSE 0 END) AS video_count,
              SUM(CASE WHEN file_type='document' THEN 1 ELSE 0 END) AS document_count,
              SUM(CASE WHEN file_type='other' OR file_type='archive' THEN 1 ELSE 0 END) AS other_count,
              SUM(CASE WHEN status='ARCHIVED' THEN 1 ELSE 0 END) AS archived_count,
              SUM(CASE WHEN status='ERROR' THEN 1 ELSE 0 END) AS error_count
            FROM files
            """
        ).fetchone()
        if rows is None:
            return {
                "total": 0,
                "image_count": 0,
                "video_count": 0,
                "document_count": 0,
                "other_count": 0,
                "archived_count": 0,
                "error_count": 0,
            }
        return {k: int(rows[k] or 0) for k in rows.keys()}
