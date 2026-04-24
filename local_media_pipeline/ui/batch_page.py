from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.services import AppServices


class BatchWorker(QObject):
    progress = Signal(str)
    finished = Signal(dict)

    def __init__(self, services: AppServices, mode: str):
        super().__init__()
        self.services = services
        self.mode = mode

    def run(self) -> None:
        try:
            if self.mode == "extract":
                result = self.services.extract_batch_to_processing(progress=self.progress.emit)
                self.finished.emit({"ok": result.success, "message": result.message})
            else:
                result = self.services.archive_ready_files(progress=self.progress.emit)
                self.finished.emit({"ok": result.success, "message": result.message})
        except Exception as exc:
            self.finished.emit({"ok": False, "message": f"任务失败：{exc}"})


class BatchPage(QWidget):
    def __init__(self, services: AppServices):
        super().__init__()
        self.services = services
        self.worker_thread: QThread | None = None
        self.worker: BatchWorker | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout()

        mode_text = "当前模式：单副本安全移动" if self.services.config.get("single_copy_mode") else "当前模式：普通复制（不删 INBOX）"
        self.mode_label = QLabel(mode_text)

        self.extract_btn = QPushButton("提取批次到 PROCESSING")
        self.archive_btn = QPushButton("归档 READY_TO_ARCHIVE")

        self.extract_btn.clicked.connect(lambda: self._start("extract"))
        self.archive_btn.clicked.connect(lambda: self._start("archive"))

        row = QHBoxLayout()
        row.addWidget(self.extract_btn)
        row.addWidget(self.archive_btn)

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)

        layout.addWidget(self.mode_label)
        layout.addLayout(row)
        layout.addWidget(self.log_box)
        self.setLayout(layout)

    def _start(self, mode: str) -> None:
        if not self.services.has_required_paths():
            QMessageBox.warning(self, "提示", "请先完成路径设置并初始化数据库。")
            return

        self.extract_btn.setEnabled(False)
        self.archive_btn.setEnabled(False)

        self.worker_thread = QThread(self)
        self.worker = BatchWorker(self.services, mode)
        self.worker.moveToThread(self.worker_thread)

        self.worker_thread.started.connect(self.worker.run)
        self.worker.progress.connect(self._append_log)
        self.worker.finished.connect(self._on_finished)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker_thread.finished.connect(self._cleanup)
        self.worker_thread.start()

    def _append_log(self, text: str) -> None:
        self.log_box.append(text)

    def _on_finished(self, payload: dict) -> None:
        self._append_log(payload.get("message", ""))
        if not payload.get("ok", False):
            QMessageBox.warning(self, "提示", payload.get("message", "任务失败"))

    def _cleanup(self) -> None:
        self.extract_btn.setEnabled(True)
        self.archive_btn.setEnabled(True)
        self.worker = None
        self.worker_thread = None
        self.mode_label.setText("当前模式：单副本安全移动" if self.services.config.get("single_copy_mode") else "当前模式：普通复制（不删 INBOX）")
