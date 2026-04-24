from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppPaths:
    inbox_path: Path
    vault_path: Path
    pipeline_root: Path
    system_dir: Path
    database_path: Path
    log_path: Path
    processing_dir: Path
    uncertain_dir: Path
    reviewed_dir: Path
    to_delete_dir: Path
    ready_to_archive_dir: Path
    temp_dir: Path
    preview_cache_dir: Path


def build_paths(config: dict) -> AppPaths:
    pipeline_root = Path(config.get("pipeline_root", ""))
    system_dir = pipeline_root / "SYSTEM"

    return AppPaths(
        inbox_path=Path(config.get("inbox_path", "")),
        vault_path=Path(config.get("vault_path", "")),
        pipeline_root=pipeline_root,
        system_dir=system_dir,
        database_path=system_dir / "pipeline.db",
        log_path=system_dir / "pipeline.log",
        processing_dir=pipeline_root / "02_PROCESSING",
        uncertain_dir=pipeline_root / "03_UNCERTAIN",
        reviewed_dir=pipeline_root / "04_REVIEWED",
        to_delete_dir=pipeline_root / "05_TO_DELETE",
        ready_to_archive_dir=pipeline_root / "06_READY_TO_ARCHIVE",
        temp_dir=pipeline_root / "TEMP",
        preview_cache_dir=pipeline_root / "TEMP" / "preview_cache",
    )


def init_pipeline_directories(paths: AppPaths) -> tuple[bool, str]:
    targets = [
        paths.system_dir,
        paths.processing_dir,
        paths.uncertain_dir,
        paths.reviewed_dir,
        paths.to_delete_dir,
        paths.ready_to_archive_dir,
        paths.temp_dir,
        paths.preview_cache_dir,
    ]
    try:
        for target in targets:
            target.mkdir(parents=True, exist_ok=True)
        return True, "目录初始化完成"
    except Exception as exc:
        return False, f"目录初始化失败：{exc}"
