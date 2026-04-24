from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.services import AppServices


class ScanWorker(QObject):
    progress = Signal(str)
    finished = Signal(dict)

    def __init__(self, services: AppServices):
        super().__init__()
        self.services = services

    def run(self) -> None:
        result = self.services.scan_inbox(progress=self.progress.emit)
        self.finished.emit(
            {
                "scanned": result.scanned_files,
                "new": result.new_files,
                "updated": result.updated_files,
                "skipped": result.skipped_files,
                "errors": result.error_files,
            }
        )


class DashboardPage(QWidget):
    def __init__(self, services: AppServices):
        super().__init__()
        self.services = services
        self.scan_thread: QThread | None = None
        self.scan_worker: ScanWorker | None = None
        self._build_ui()
        self.refresh_stats()

    def _build_ui(self) -> None:
        root = QVBoxLayout()

        path_box = QGroupBox("路径信息")
        path_form = QFormLayout()
        self.db_path_label = QLabel(str(self.services.paths.database_path))
        self.inbox_path_label = QLabel(str(self.services.paths.inbox_root))
        path_form.addRow("当前数据库路径：", self.db_path_label)
        path_form.addRow("INBOX 路径：", self.inbox_path_label)
        path_box.setLayout(path_form)

        stats_box = QGroupBox("统计")
        stats_form = QFormLayout()
        self.total_label = QLabel("0")
        self.image_label = QLabel("0")
        self.video_label = QLabel("0")
        self.document_label = QLabel("0")
        self.other_label = QLabel("0")
        self.archived_label = QLabel("0")
        self.error_label = QLabel("0")

        stats_form.addRow("文件总数：", self.total_label)
        stats_form.addRow("图片数量：", self.image_label)
        stats_form.addRow("视频数量：", self.video_label)
        stats_form.addRow("文档数量：", self.document_label)
        stats_form.addRow("其他数量：", self.other_label)
        stats_form.addRow("已归档数量：", self.archived_label)
        stats_form.addRow("ERROR 数量：", self.error_label)
        stats_box.setLayout(stats_form)

        btn_row = QHBoxLayout()
        self.init_btn = QPushButton("初始化数据库")
        self.scan_btn = QPushButton("扫描 INBOX")
        self.init_btn.clicked.connect(self.on_init_db)
        self.scan_btn.clicked.connect(self.on_scan)
        btn_row.addWidget(self.init_btn)
        btn_row.addWidget(self.scan_btn)

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setPlaceholderText("日志输出...")

        root.addWidget(path_box)
        root.addWidget(stats_box)
        root.addLayout(btn_row)
        root.addWidget(self.log_box)
        self.setLayout(root)

    def append_log(self, text: str) -> None:
        self.log_box.append(text)
        try:
            self.services.db.insert_log("INFO", "ui.dashboard", text)
        except Exception:
            pass

    def on_init_db(self) -> None:
        ok, message = self.services.initialize_database()
        self.append_log(message)
        if not ok:
            QMessageBox.warning(self, "初始化失败", message)
        self.refresh_stats()

    def on_scan(self) -> None:
        self.scan_btn.setEnabled(False)
        self.append_log("开始扫描 INBOX...")

        self.scan_thread = QThread(self)
        self.scan_worker = ScanWorker(self.services)
        self.scan_worker.moveToThread(self.scan_thread)

        self.scan_thread.started.connect(self.scan_worker.run)
        self.scan_worker.progress.connect(self.append_log)
        self.scan_worker.finished.connect(self._on_scan_finished)
        self.scan_worker.finished.connect(self.scan_thread.quit)
        self.scan_thread.finished.connect(self._cleanup_scan_thread)
        self.scan_thread.start()

    def _on_scan_finished(self, stats: dict) -> None:
        self.append_log(
            f"扫描任务结束：总计={stats['scanned']}，新增={stats['new']}，"
            f"更新={stats['updated']}，跳过={stats['skipped']}，错误={stats['errors']}"
        )
        self.scan_btn.setEnabled(True)
        self.refresh_stats()

    def _cleanup_scan_thread(self) -> None:
        self.scan_worker = None
        self.scan_thread = None

    def refresh_stats(self) -> None:
        try:
            if self.services.db.conn is None:
                self.total_label.setText("0")
                self.image_label.setText("0")
                self.video_label.setText("0")
                self.document_label.setText("0")
                self.other_label.setText("0")
                self.archived_label.setText("0")
                self.error_label.setText("0")
                return
            s = self.services.db.get_dashboard_stats()
            self.total_label.setText(str(s["total"]))
            self.image_label.setText(str(s["image_count"]))
            self.video_label.setText(str(s["video_count"]))
            self.document_label.setText(str(s["document_count"]))
            self.other_label.setText(str(s["other_count"]))
            self.archived_label.setText(str(s["archived_count"]))
            self.error_label.setText(str(s["error_count"]))
        except Exception as exc:
            self.append_log(f"刷新统计失败：{exc}")
