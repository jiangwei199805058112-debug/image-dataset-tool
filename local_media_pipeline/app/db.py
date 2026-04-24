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

    def init_schema(self) -> None:
        assert self.conn is not None
        for sql in schema.TABLES_SQL:
            self.conn.execute(sql)
        for sql in schema.INDEXES_SQL:
            self.conn.execute(sql)
        self._migrate_schema()
        self.conn.commit()

    def _migrate_schema(self) -> None:
        assert self.conn is not None
        def columns(table: str) -> set[str]:
            rows = self.conn.execute(f"PRAGMA table_info({table})").fetchall()
            return {str(r[1]) for r in rows}

        ss = columns("scan_sessions")
        adds = {
            "last_scanned_path": "TEXT",
            "skipped_files": "INTEGER DEFAULT 0",
            "error_files": "INTEGER DEFAULT 0",
            "updated_at": "INTEGER",
        }
        for col, typ in adds.items():
            if col not in ss:
                self.conn.execute(f"ALTER TABLE scan_sessions ADD COLUMN {col} {typ}")

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

    def insert_log(self, level: str, module: str, message: str, target_type: str | None = None, target_id: str | None = None) -> None:
        now = int(time.time())
        self.execute(
            "INSERT INTO logs(level,module,target_type,target_id,message,created_at) VALUES (?,?,?,?,?,?)",
            (level, module, target_type, target_id, message, now),
        )
        self.commit()

    def get_dashboard_stats(self) -> dict[str, int]:
        row = self.execute(
            """
            SELECT
              COUNT(*) AS total,
              SUM(CASE WHEN file_type='image' THEN 1 ELSE 0 END) AS image_count,
              SUM(CASE WHEN file_type='raw_image' THEN 1 ELSE 0 END) AS raw_image_count,
              SUM(CASE WHEN file_type='video' THEN 1 ELSE 0 END) AS video_count,
              SUM(CASE WHEN file_type='document' THEN 1 ELSE 0 END) AS document_count,
              SUM(CASE WHEN file_type='archive' THEN 1 ELSE 0 END) AS archive_count,
              SUM(CASE WHEN file_type='software' THEN 1 ELSE 0 END) AS software_count,
              SUM(CASE WHEN file_type='audio' THEN 1 ELSE 0 END) AS audio_count,
              SUM(CASE WHEN file_type='other' THEN 1 ELSE 0 END) AS other_count,
              SUM(CASE WHEN status='ARCHIVED' THEN 1 ELSE 0 END) AS archived_count,
              SUM(CASE WHEN status='ERROR' THEN 1 ELSE 0 END) AS error_count
            FROM files
            """
        ).fetchone()
        return {k: int((row[k] if row else 0) or 0) for k in [
            "total","image_count","raw_image_count","video_count","document_count","archive_count","software_count","audio_count","other_count","archived_count","error_count"
        ]}

    def get_latest_scan_session(self, root_path: str):
        return self.execute("SELECT * FROM scan_sessions WHERE root_path=? ORDER BY id DESC LIMIT 1", (root_path,)).fetchone()

    def create_scan_session(self, root_path: str, note: str = "") -> int:
        now = int(time.time())
        cur = self.execute(
            """
            INSERT INTO scan_sessions(root_path,status,scanned_files,new_files,updated_files,skipped_files,error_files,started_at,updated_at,note)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (root_path, "RUNNING", 0, 0, 0, 0, 0, now, now, note),
        )
        self.commit()
        return int(cur.lastrowid)

    def update_scan_session(self, session_id: int, status: str, last_scanned_path: str | None, scanned: int, new: int, updated: int, skipped: int, errors: int, note: str = "") -> None:
        now = int(time.time())
        self.execute(
            """
            UPDATE scan_sessions
            SET status=?, last_scanned_path=?, scanned_files=?, new_files=?, updated_files=?, skipped_files=?, error_files=?, updated_at=?, note=?
            WHERE id=?
            """,
            (status, last_scanned_path, scanned, new, updated, skipped, errors, now, note, session_id),
        )
        self.commit()

    def finish_scan_session(self, session_id: int, status: str, note: str = "") -> None:
        now = int(time.time())
        self.execute("UPDATE scan_sessions SET status=?, updated_at=?, finished_at=?, note=? WHERE id=?", (status, now, now, note, session_id))
        self.commit()

    def get_confirmed_type(self, ext: str) -> str | None:
        row = self.execute("SELECT confirmed_type FROM extension_stats WHERE ext=?", (ext,)).fetchone()
        return str(row["confirmed_type"]) if row and row["confirmed_type"] else None

    def upsert_extension_stat(self, ext: str, guessed_type: str, is_known: int) -> None:
        now = int(time.time())
        self.execute(
            """
            INSERT INTO extension_stats(ext,detected_count,guessed_type,is_known,first_seen_at,last_seen_at)
            VALUES (?,1,?,?,?,?)
            ON CONFLICT(ext) DO UPDATE SET
              detected_count=detected_count+1,
              guessed_type=excluded.guessed_type,
              is_known=CASE WHEN extension_stats.confirmed_type IS NOT NULL THEN 1 ELSE excluded.is_known END,
              last_seen_at=excluded.last_seen_at
            """,
            (ext, guessed_type, is_known, now, now),
        )
        self.commit()

    def get_unknown_extensions(self, threshold: int = 10) -> list[sqlite3.Row]:
        return self.execute(
            """
            SELECT ext, detected_count, COALESCE(confirmed_type, guessed_type, 'other') AS guessed_type
            FROM extension_stats
            WHERE is_known=0 AND is_ignored=0 AND detected_count>=?
            ORDER BY detected_count DESC
            """,
            (threshold,),
        ).fetchall()

    def confirm_extension_type(self, ext: str, file_type: str, ignored: int = 0) -> None:
        now = int(time.time())
        self.execute(
            """
            INSERT INTO extension_stats(ext,detected_count,guessed_type,confirmed_type,is_known,is_ignored,first_seen_at,last_seen_at)
            VALUES (?,0,?,?,?, ?,?,?)
            ON CONFLICT(ext) DO UPDATE SET
              confirmed_type=excluded.confirmed_type,
              guessed_type=excluded.guessed_type,
              is_known=excluded.is_known,
              is_ignored=excluded.is_ignored,
              last_seen_at=excluded.last_seen_at
            """,
            (ext, file_type, file_type, 0 if ignored else 1, ignored, now, now),
        )
        if not ignored:
            self.execute("UPDATE files SET file_type=? WHERE file_ext=?", (file_type, ext))
        self.commit()

    # existing methods
    def fetch_candidate_batch_files(self, limit_bytes: int) -> list[sqlite3.Row]:
        rows = self.execute("SELECT id,current_path,file_name,file_size,status FROM files WHERE status IN ('SURVEYED','INBOX') ORDER BY mtime ASC").fetchall()
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
        return self.execute("SELECT id,current_path,file_name,category,event_id,mtime FROM files WHERE status='READY_TO_ARCHIVE' ORDER BY updated_at ASC LIMIT ?", (limit,)).fetchall()

    def create_archive_job(self, batch_id: str | None, target_type: str, target_id: str, source_path: str, temp_path: str, final_path: str) -> int:
        cur = self.execute("INSERT INTO archive_jobs(batch_id,target_type,target_id,source_path,temp_path,final_path,status,started_at) VALUES (?,?,?,?,?,?,?,?)", (batch_id,target_type,target_id,source_path,temp_path,final_path,"COPYING",int(time.time())))
        self.commit()
        return int(cur.lastrowid)

    def update_archive_job(self, job_id: int, status: str, source_hash: str | None = None, target_hash: str | None = None, bytes_copied: int | None = None, error_message: str | None = None) -> None:
        self.execute("UPDATE archive_jobs SET status=?,source_hash=COALESCE(?,source_hash),target_hash=COALESCE(?,target_hash),bytes_copied=COALESCE(?,bytes_copied),error_message=?,finished_at=CASE WHEN ? IN ('FAILED','CLEANED') THEN ? ELSE finished_at END WHERE id=?", (status,source_hash,target_hash,bytes_copied,error_message,status,int(time.time()),job_id))
        self.commit()

    def mark_file_staged(self, file_id: int, new_path: str, batch_id: str) -> None:
        self.execute("UPDATE files SET current_path=?,status='STAGED',batch_id_last=?,error_message=NULL,updated_at=? WHERE id=?", (new_path,batch_id,int(time.time()),file_id)); self.commit()

    def mark_file_archived(self, file_id: int, new_path: str) -> None:
        self.execute("UPDATE files SET current_path=?,archived_path=?,status='ARCHIVED',error_message=NULL,updated_at=? WHERE id=?", (new_path,new_path,int(time.time()),file_id)); self.commit()

    def mark_file_error(self, file_id: int, message: str, fallback_status: str = "ERROR") -> None:
        self.execute("UPDATE files SET status=?,error_message=?,updated_at=? WHERE id=?", (fallback_status,message,int(time.time()),file_id)); self.commit()

    def create_batch(self, batch_id: str, name: str, target_path: str, total_files: int, total_size: int) -> None:
        self.execute("INSERT INTO batches(id,name,source_scope,target_path,total_files,total_size_bytes,gap_mode,status,started_at) VALUES (?,?,?,?,?,?,?,?,?)", (batch_id,name,"INBOX",target_path,total_files,total_size,"NORMAL","STAGING",int(time.time()))); self.commit()

    def finish_batch(self, batch_id: str, status: str, note: str = "") -> None:
        self.execute("UPDATE batches SET status=?,finished_at=?,note=? WHERE id=?", (status,int(time.time()),note,batch_id)); self.commit()
