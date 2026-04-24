from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox

from app.services import AppServices
from ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    project_root = Path(__file__).resolve().parent
    services = AppServices(project_root)

    window = MainWindow(services)
    window.show()

    if not services.has_required_paths() or not services.paths.inbox_path.exists():
        QMessageBox.information(window, "提示", "请先设置路径")
        window.dashboard.open_path_settings()

    init_ok, init_msg = services.initialize_database()
    window.dashboard.append_log(init_msg)
    if not init_ok:
        QMessageBox.warning(window, "初始化提示", init_msg)
    window.dashboard.refresh_path_labels()
    window.dashboard.refresh_stats()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
