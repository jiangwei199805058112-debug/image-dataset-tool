from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppPaths:
    inbox_root: Path
    vault_root: Path
    meta_backup_root: Path
    pipeline_root: Path
    system_dir: Path
    processing_dir: Path
    uncertain_pending_dir: Path
    uncertain_snoozed_dir: Path
    uncertain_hard_cases_dir: Path
    reviewed_dir: Path
    to_delete_duplicates_dir: Path
    to_delete_manual_dir: Path
    ready_to_archive_dir: Path
    temp_dir: Path
    preview_cache_dir: Path
    database_path: Path
    log_path: Path
    runtime_config_path: Path


class PathInitError(Exception):
    pass


def build_paths(config: dict) -> AppPaths:
    p = config["paths"]
    return AppPaths(
        inbox_root=Path(p["inbox_root"]),
        vault_root=Path(p["vault_root"]),
        meta_backup_root=Path(p["meta_backup_root"]),
        pipeline_root=Path(p["pipeline_root"]),
        system_dir=Path(p["system_dir"]),
        processing_dir=Path(p["processing_dir"]),
        uncertain_pending_dir=Path(p["uncertain_pending_dir"]),
        uncertain_snoozed_dir=Path(p["uncertain_snoozed_dir"]),
        uncertain_hard_cases_dir=Path(p["uncertain_hard_cases_dir"]),
        reviewed_dir=Path(p["reviewed_dir"]),
        to_delete_duplicates_dir=Path(p["to_delete_duplicates_dir"]),
        to_delete_manual_dir=Path(p["to_delete_manual_dir"]),
        ready_to_archive_dir=Path(p["ready_to_archive_dir"]),
        temp_dir=Path(p["temp_dir"]),
        preview_cache_dir=Path(p["preview_cache_dir"]),
        database_path=Path(p["database_path"]),
        log_path=Path(p["log_path"]),
        runtime_config_path=Path(p["runtime_config_path"]),
    )


def init_directories(paths: AppPaths) -> tuple[bool, str]:
    create_targets = [
        paths.inbox_root,
        paths.vault_root,
        paths.meta_backup_root,
        paths.pipeline_root,
        paths.system_dir,
        paths.processing_dir,
        paths.uncertain_pending_dir,
        paths.uncertain_snoozed_dir,
        paths.uncertain_hard_cases_dir,
        paths.reviewed_dir,
        paths.to_delete_duplicates_dir,
        paths.to_delete_manual_dir,
        paths.ready_to_archive_dir,
        paths.temp_dir,
        paths.preview_cache_dir,
    ]
    try:
        for target in create_targets:
            target.mkdir(parents=True, exist_ok=True)
    except Exception as exc:  # pragma: no cover
        return False, f"目录初始化失败，请检查 L: 或 D: 是否可用。错误：{exc}"
    return True, "目录初始化完成"
