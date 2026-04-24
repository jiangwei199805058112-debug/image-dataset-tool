from __future__ import annotations

PRAGMAS = [
    "PRAGMA journal_mode=WAL;",
    "PRAGMA synchronous=NORMAL;",
    "PRAGMA foreign_keys=ON;",
]

TABLES_SQL = [
    """
    CREATE TABLE IF NOT EXISTS files (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      file_uid TEXT UNIQUE NOT NULL,
      original_path TEXT NOT NULL,
      current_path TEXT NOT NULL,
      relative_path TEXT,
      file_name TEXT NOT NULL,
      file_ext TEXT,
      file_type TEXT,
      file_size INTEGER,
      mtime INTEGER,
      ctime INTEGER,
      exif_time INTEGER,
      media_time INTEGER,
      virtual_time INTEGER,
      device_model TEXT,
      device_key TEXT,
      width INTEGER,
      height INTEGER,
      duration_ms INTEGER,
      quick_hash TEXT,
      sample_hash TEXT,
      full_hash TEXT,
      event_id TEXT,
      batch_id_last TEXT,
      status TEXT NOT NULL,
      category TEXT,
      subcategory TEXT,
      confidence REAL,
      review_required INTEGER DEFAULT 0,
      is_auto_pass INTEGER DEFAULT 0,
      is_duplicate_exact INTEGER DEFAULT 0,
      duplicate_of_file_id INTEGER,
      is_suspected_duplicate INTEGER DEFAULT 0,
      suspected_duplicate_group TEXT,
      snooze_count INTEGER DEFAULT 0,
      snooze_until INTEGER,
      archived_path TEXT,
      deleted_at INTEGER,
      error_message TEXT,
      created_at INTEGER,
      updated_at INTEGER
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS events (
      id TEXT PRIMARY KEY,
      start_time INTEGER,
      end_time INTEGER,
      file_count INTEGER DEFAULT 0,
      image_count INTEGER DEFAULT 0,
      video_count INTEGER DEFAULT 0,
      total_size_bytes INTEGER DEFAULT 0,
      device_key TEXT,
      gap_mode TEXT,
      category TEXT,
      subcategory TEXT,
      confidence REAL,
      review_required INTEGER DEFAULT 0,
      preview_path TEXT,
      status TEXT,
      is_manually_merged INTEGER DEFAULT 0,
      created_at INTEGER,
      updated_at INTEGER
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS batches (
      id TEXT PRIMARY KEY,
      name TEXT,
      source_scope TEXT,
      target_path TEXT,
      total_files INTEGER DEFAULT 0,
      total_size_bytes INTEGER DEFAULT 0,
      gap_mode TEXT,
      status TEXT,
      started_at INTEGER,
      finished_at INTEGER,
      note TEXT
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS reviews (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      target_type TEXT NOT NULL,
      target_id TEXT NOT NULL,
      action TEXT NOT NULL,
      category TEXT,
      subcategory TEXT,
      applied_scope TEXT,
      old_status TEXT,
      new_status TEXT,
      note TEXT,
      operator TEXT DEFAULT 'local_user',
      created_at INTEGER
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS archive_jobs (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      batch_id TEXT,
      target_type TEXT,
      target_id TEXT,
      source_path TEXT,
      temp_path TEXT,
      final_path TEXT,
      source_hash TEXT,
      target_hash TEXT,
      bytes_copied INTEGER DEFAULT 0,
      status TEXT,
      error_message TEXT,
      started_at INTEGER,
      finished_at INTEGER
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS delete_queue (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      file_id INTEGER,
      reason TEXT,
      queue_type TEXT,
      scheduled_delete_at INTEGER,
      deleted_at INTEGER,
      recoverable INTEGER DEFAULT 1,
      note TEXT,
      created_at INTEGER
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS device_time_offsets (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      device_key TEXT NOT NULL,
      offset_seconds INTEGER NOT NULL,
      scope_type TEXT,
      scope_value TEXT,
      valid_from INTEGER,
      valid_to INTEGER,
      anchor_ref_file_id INTEGER,
      anchor_shifted_file_id INTEGER,
      note TEXT,
      created_at INTEGER
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS scan_sessions (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      root_path TEXT,
      status TEXT,
      last_scanned_path TEXT,
      scanned_files INTEGER DEFAULT 0,
      new_files INTEGER DEFAULT 0,
      updated_files INTEGER DEFAULT 0,
      skipped_files INTEGER DEFAULT 0,
      error_files INTEGER DEFAULT 0,
      started_at INTEGER,
      updated_at INTEGER,
      finished_at INTEGER,
      note TEXT
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS extension_stats (
      ext TEXT PRIMARY KEY,
      detected_count INTEGER DEFAULT 0,
      guessed_type TEXT,
      confirmed_type TEXT,
      is_known INTEGER DEFAULT 0,
      is_ignored INTEGER DEFAULT 0,
      first_seen_at INTEGER,
      last_seen_at INTEGER
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS logs (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      level TEXT,
      module TEXT,
      target_type TEXT,
      target_id TEXT,
      message TEXT,
      created_at INTEGER
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS settings_runtime (
      key TEXT PRIMARY KEY,
      value TEXT,
      updated_at INTEGER
    );
    """,
]

INDEXES_SQL = [
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_files_current_path_unique ON files(current_path);",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_files_file_uid_unique ON files(file_uid);",
    "CREATE INDEX IF NOT EXISTS idx_files_status ON files(status);",
    "CREATE INDEX IF NOT EXISTS idx_files_file_type ON files(file_type);",
    "CREATE INDEX IF NOT EXISTS idx_files_full_hash ON files(full_hash);",
    "CREATE INDEX IF NOT EXISTS idx_files_quick_hash ON files(quick_hash);",
    "CREATE INDEX IF NOT EXISTS idx_files_virtual_time ON files(virtual_time);",
    "CREATE INDEX IF NOT EXISTS idx_files_event_id ON files(event_id);",
    "CREATE INDEX IF NOT EXISTS idx_files_device_key ON files(device_key);",
    "CREATE INDEX IF NOT EXISTS idx_files_snooze_until ON files(snooze_until);",
    "CREATE INDEX IF NOT EXISTS idx_files_is_suspected_duplicate ON files(is_suspected_duplicate);",
    "CREATE INDEX IF NOT EXISTS idx_events_status ON events(status);",
    "CREATE INDEX IF NOT EXISTS idx_events_start_time ON events(start_time);",
    "CREATE INDEX IF NOT EXISTS idx_batches_status ON batches(status);",
    "CREATE INDEX IF NOT EXISTS idx_reviews_target_type_target_id ON reviews(target_type, target_id);",
    "CREATE INDEX IF NOT EXISTS idx_archive_jobs_status ON archive_jobs(status);",
]
