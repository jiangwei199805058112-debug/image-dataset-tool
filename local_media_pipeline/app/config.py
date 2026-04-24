from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_CONFIG: dict[str, str] = {
    "inbox_path": "",
    "vault_path": "",
    "pipeline_root": "",
}


def _config_file(project_root: Path) -> Path:
    return project_root / "config.json"


def load_config(project_root: Path) -> dict[str, Any]:
    config_path = _config_file(project_root)
    if not config_path.exists():
        save_config(project_root, DEFAULT_CONFIG)
        return dict(DEFAULT_CONFIG)

    with config_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    merged = dict(DEFAULT_CONFIG)
    merged.update(data)
    return merged


def save_config(project_root: Path, config: dict[str, Any]) -> None:
    config_path = _config_file(project_root)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(DEFAULT_CONFIG)
    payload.update(config)
    with config_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
