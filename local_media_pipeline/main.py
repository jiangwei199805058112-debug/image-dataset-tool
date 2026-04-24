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

    init_ok, init_msg = services.initialize_database()
    if not init_ok:
        QMessageBox.warning(window, "初始化提示", init_msg)
        window.dashboard.append_log(init_msg)
    else:
        window.dashboard.append_log(init_msg)
        window.dashboard.refresh_stats()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
