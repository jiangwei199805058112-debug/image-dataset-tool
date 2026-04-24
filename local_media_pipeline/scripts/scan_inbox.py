from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services import AppServices


if __name__ == "__main__":
    services = AppServices(ROOT)
    ok, message = services.initialize_database()
    print(message)
    if not ok:
        raise SystemExit(1)

    result = services.scan_inbox(progress=print)
    print(
        f"扫描完成：总计={result.scanned_files}, 新增={result.new_files}, 更新={result.updated_files}, "
        f"跳过={result.skipped_files}, 错误={result.error_files}"
    )
