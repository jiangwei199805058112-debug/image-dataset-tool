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

    @staticmethod
    def create_connection(db_path: Path) -> sqlite3.Connection:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        for pragma in schema.PRAGMAS:
            conn.execute(pragma)
        conn.commit()
        return conn

    def connect(self) -> None:
        self.conn = self.create_connection(self.db_path)

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
            return {"total": 0, "image_count": 0, "video_count": 0, "document_count": 0, "other_count": 0, "archived_count": 0, "error_count": 0}
        return {k: int(rows[k] or 0) for k in rows.keys()}

    def fetch_candidate_batch_files(self, limit_bytes: int) -> list[sqlite3.Row]:
        rows = self.execute(
            """
            SELECT id, current_path, file_name, file_size, status
            FROM files
            WHERE status IN ('SURVEYED', 'INBOX')
            ORDER BY mtime ASC
            """
        ).fetchall()
        picked: list[sqlite3.Row] = []
        total = 0
        for row in rows:
            size = int(row["file_size"] or 0)
            if total + size > limit_bytes and picked:
                break
            total += size
            picked.append(row)
        return picked

    def fetch_ready_to_archive_files(self, limit: int = 2000) -> list[sqlite3.Row]:
        return self.execute(
            """
            SELECT id, current_path, file_name, category, event_id, mtime
            FROM files
            WHERE status='READY_TO_ARCHIVE'
            ORDER BY updated_at ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    def create_archive_job(self, batch_id: str | None, target_type: str, target_id: str, source_path: str, temp_path: str, final_path: str) -> int:
        cur = self.execute(
            """
            INSERT INTO archive_jobs(batch_id, target_type, target_id, source_path, temp_path, final_path, status, started_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (batch_id, target_type, target_id, source_path, temp_path, final_path, "COPYING", int(time.time())),
        )
        self.commit()
        return int(cur.lastrowid)

    def update_archive_job(
        self,
        job_id: int,
        status: str,
        source_hash: str | None = None,
        target_hash: str | None = None,
        bytes_copied: int | None = None,
        error_message: str | None = None,
    ) -> None:
        self.execute(
            """
            UPDATE archive_jobs
            SET status=?, source_hash=COALESCE(?, source_hash), target_hash=COALESCE(?, target_hash),
                bytes_copied=COALESCE(?, bytes_copied), error_message=?,
                finished_at=CASE WHEN ? IN ('FAILED', 'CLEANED') THEN ? ELSE finished_at END
            WHERE id=?
            """,
            (
                status,
                source_hash,
                target_hash,
                bytes_copied,
                error_message,
                status,
                int(time.time()),
                job_id,
            ),
        )
        self.commit()

    def mark_file_staged(self, file_id: int, new_path: str, batch_id: str) -> None:
        self.execute(
            """
            UPDATE files
            SET current_path=?, status='STAGED', batch_id_last=?, error_message=NULL, updated_at=?
            WHERE id=?
            """,
            (new_path, batch_id, int(time.time()), file_id),
        )
        self.commit()

    def mark_file_archived(self, file_id: int, new_path: str) -> None:
        self.execute(
            """
            UPDATE files
            SET current_path=?, archived_path=?, status='ARCHIVED', error_message=NULL, updated_at=?
            WHERE id=?
            """,
            (new_path, new_path, int(time.time()), file_id),
        )
        self.commit()

    def mark_file_error(self, file_id: int, message: str, fallback_status: str = "ERROR") -> None:
        self.execute(
            """
            UPDATE files
            SET status=?, error_message=?, updated_at=?
            WHERE id=?
            """,
            (fallback_status, message, int(time.time()), file_id),
        )
        self.commit()

    def create_batch(self, batch_id: str, name: str, target_path: str, total_files: int, total_size: int) -> None:
        self.execute(
            """
            INSERT INTO batches(id, name, source_scope, target_path, total_files, total_size_bytes, gap_mode, status, started_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (batch_id, name, "INBOX", target_path, total_files, total_size, "NORMAL", "STAGING", int(time.time())),
        )
        self.commit()

    def finish_batch(self, batch_id: str, status: str, note: str = "") -> None:
        self.execute(
            "UPDATE batches SET status=?, finished_at=?, note=? WHERE id=?",
            (status, int(time.time()), note, batch_id),
        )
        self.commit()
