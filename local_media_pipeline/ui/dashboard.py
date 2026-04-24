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

from app.scanner import ScanControl
from app.services import AppServices
from ui.path_settings_dialog import PathSettingsDialog


class ScanWorker(QObject):
    progress = Signal(str)
    finished = Signal(dict)

    def __init__(self, services: AppServices, control: ScanControl):
        super().__init__()
        self.services = services
        self.control = control

    def run(self) -> None:
        try:
            result = self.services.scan_inbox(progress=self.progress.emit, control=self.control)
            self.finished.emit({"ok": True, "scanned": result.scanned_files, "new": result.new_files, "updated": result.updated_files, "skipped": result.skipped_files, "errors": result.error_files})
        except Exception as exc:
            self.progress.emit(f"扫描失败：{exc}")
            self.finished.emit({"ok": False, "scanned": 0, "new": 0, "updated": 0, "skipped": 0, "errors": 1})


class DashboardPage(QWidget):
    def __init__(self, services: AppServices):
        super().__init__()
        self.services = services
        self.scan_thread: QThread | None = None
        self.scan_worker: ScanWorker | None = None
        self.scan_control: ScanControl | None = None
        self._build_ui()
        self.refresh_path_labels()
        self.refresh_stats()
        self.refresh_unknown_extensions()

    def _build_ui(self) -> None:
        root = QVBoxLayout()

        path_box = QGroupBox("路径信息")
        path_form = QFormLayout()
        self.db_path_label = QLabel("")
        self.inbox_path_label = QLabel("")
        self.vault_path_label = QLabel("")
        self.pipeline_root_label = QLabel("")
        path_form.addRow("当前数据库路径：", self.db_path_label)
        path_form.addRow("INBOX 路径：", self.inbox_path_label)
        path_form.addRow("VAULT 路径：", self.vault_path_label)
        path_form.addRow("PIPELINE_ROOT：", self.pipeline_root_label)
        path_box.setLayout(path_form)

        stats_box = QGroupBox("统计")
        stats_form = QFormLayout()
        self.total_label = QLabel("0")
        self.image_label = QLabel("0")
        self.raw_label = QLabel("0")
        self.video_label = QLabel("0")
        self.document_label = QLabel("0")
        self.archive_label = QLabel("0")
        self.software_label = QLabel("0")
        self.audio_label = QLabel("0")
        self.other_label = QLabel("0")
        self.archived_label = QLabel("0")
        self.error_label = QLabel("0")

        stats_form.addRow("文件总数：", self.total_label)
        stats_form.addRow("图片数量：", self.image_label)
        stats_form.addRow("RAW 图片数量：", self.raw_label)
        stats_form.addRow("视频数量：", self.video_label)
        stats_form.addRow("文档数量：", self.document_label)
        stats_form.addRow("压缩包数量：", self.archive_label)
        stats_form.addRow("软件数量：", self.software_label)
        stats_form.addRow("音频数量：", self.audio_label)
        stats_form.addRow("其他数量：", self.other_label)
        stats_form.addRow("已归档数量：", self.archived_label)
        stats_form.addRow("ERROR 数量：", self.error_label)
        stats_box.setLayout(stats_form)

        btn_row = QHBoxLayout()
        self.path_btn = QPushButton("设置路径")
        self.init_btn = QPushButton("初始化数据库")
        self.scan_btn = QPushButton("扫描 INBOX")
        self.pause_btn = QPushButton("暂停扫描")
        self.stop_btn = QPushButton("停止扫描")
        self.pause_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.path_btn.clicked.connect(self.open_path_settings)
        self.init_btn.clicked.connect(self.on_init_db)
        self.scan_btn.clicked.connect(self.on_scan)
        self.pause_btn.clicked.connect(self.on_pause_resume)
        self.stop_btn.clicked.connect(self.on_stop)
        for b in [self.path_btn, self.init_btn, self.scan_btn, self.pause_btn, self.stop_btn]:
            btn_row.addWidget(b)

        self.unknown_box = QGroupBox("未知类型提示区")
        self.unknown_layout = QVBoxLayout()
        self.unknown_box.setLayout(self.unknown_layout)

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setPlaceholderText("日志输出...")

        root.addWidget(path_box)
        root.addWidget(stats_box)
        root.addLayout(btn_row)
        root.addWidget(self.unknown_box)
        root.addWidget(self.log_box)
        self.setLayout(root)

    def refresh_path_labels(self) -> None:
        self.db_path_label.setText(str(self.services.paths.database_path))
        self.inbox_path_label.setText(str(self.services.paths.inbox_path))
        self.vault_path_label.setText(str(self.services.paths.vault_path))
        self.pipeline_root_label.setText(str(self.services.paths.pipeline_root))

    def append_log(self, text: str) -> None:
        self.log_box.append(text)

    def open_path_settings(self) -> None:
        dialog = PathSettingsDialog(self.services, self)
        if dialog.exec():
            self.refresh_path_labels()
            self.append_log("路径配置已更新")
            self.refresh_stats()
            self.refresh_unknown_extensions()

    def on_init_db(self) -> None:
        ok, message = self.services.initialize_database()
        self.append_log(message)
        if not ok:
            QMessageBox.warning(self, "初始化失败", message)
        self.refresh_path_labels()
        self.refresh_stats()
        self.refresh_unknown_extensions()

    def on_scan(self) -> None:
        if not self.services.has_required_paths() or not self.services.paths.inbox_path.exists():
            QMessageBox.warning(self, "提示", "INBOX 路径不存在，请先设置路径。")
            self.open_path_settings()
            return

        self.scan_btn.setEnabled(False)
        self.pause_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)
        self.pause_btn.setText("暂停扫描")

        self.scan_control = ScanControl()
        self.scan_thread = QThread(self)
        self.scan_worker = ScanWorker(self.services, self.scan_control)
        self.scan_worker.moveToThread(self.scan_thread)
        self.scan_thread.started.connect(self.scan_worker.run)
        self.scan_worker.progress.connect(self._on_scan_progress)
        self.scan_worker.finished.connect(self._on_scan_finished)
        self.scan_worker.finished.connect(self.scan_thread.quit)
        self.scan_thread.finished.connect(self._cleanup_scan_thread)
        self.scan_thread.start()

    def on_pause_resume(self) -> None:
        if self.scan_control is None:
            return
        if not self.scan_control.pause_event.is_set():
            self.scan_control.request_pause()
            self.pause_btn.setText("继续扫描")
        else:
            self.scan_control.request_resume()
            self.pause_btn.setText("暂停扫描")

    def on_stop(self) -> None:
        if self.scan_control is not None:
            self.scan_control.request_stop()

    def _on_scan_progress(self, message: str) -> None:
        self.append_log(message)
        if "已扫描：" in message:
            self.refresh_stats()
        if "未知扩展名" in message:
            self.refresh_unknown_extensions()

    def _on_scan_finished(self, stats: dict) -> None:
        self.append_log(f"扫描任务结束：总计={stats['scanned']}，新增={stats['new']}，更新={stats['updated']}，跳过={stats['skipped']}，错误={stats['errors']}")
        self.scan_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.pause_btn.setText("暂停扫描")
        self.refresh_stats()
        self.refresh_unknown_extensions()

    def _cleanup_scan_thread(self) -> None:
        self.scan_worker = None
        self.scan_thread = None
        self.scan_control = None

    def refresh_stats(self) -> None:
        try:
            if self.services.db.conn is None:
                self.services.db.connect(); self.services.db.init_schema()
            s = self.services.db.get_dashboard_stats()
            self.total_label.setText(str(s["total"]))
            self.image_label.setText(str(s["image_count"]))
            self.raw_label.setText(str(s["raw_image_count"]))
            self.video_label.setText(str(s["video_count"]))
            self.document_label.setText(str(s["document_count"]))
            self.archive_label.setText(str(s["archive_count"]))
            self.software_label.setText(str(s["software_count"]))
            self.audio_label.setText(str(s["audio_count"]))
            self.other_label.setText(str(s["other_count"]))
            self.archived_label.setText(str(s["archived_count"]))
            self.error_label.setText(str(s["error_count"]))
        except Exception as exc:
            self.append_log(f"刷新统计失败：{exc}")

    def refresh_unknown_extensions(self) -> None:
        while self.unknown_layout.count():
            item = self.unknown_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        try:
            rows = self.services.get_unknown_extensions()
            if not rows:
                self.unknown_layout.addWidget(QLabel("暂无需要确认的未知扩展名。"))
                return
            for row in rows:
                ext = str(row["ext"])
                cnt = int(row["detected_count"] or 0)
                guessed = str(row["guessed_type"] or "other")
                line = QHBoxLayout()
                line.addWidget(QLabel(f"{ext} | 数量={cnt} | 猜测={guessed}"))
                actions = [
                    ("设为图片", "image"), ("设为RAW", "raw_image"), ("设为视频", "video"),
                    ("设为文档", "document"), ("设为压缩包", "archive"), ("设为软件", "software"), ("设为音频", "audio")
                ]
                for text, tp in actions:
                    btn = QPushButton(text)
                    btn.clicked.connect(lambda _=False, e=ext, t=tp: self._confirm_extension(e, t, False))
                    line.addWidget(btn)
                ignore_btn = QPushButton("忽略")
                ignore_btn.clicked.connect(lambda _=False, e=ext: self._confirm_extension(e, "other", True))
                line.addWidget(ignore_btn)
                box = QWidget()
                box.setLayout(line)
                self.unknown_layout.addWidget(box)
        except Exception as exc:
            self.unknown_layout.addWidget(QLabel(f"未知类型加载失败：{exc}"))

    def _confirm_extension(self, ext: str, file_type: str, ignored: bool) -> None:
        try:
            self.services.confirm_extension_type(ext, file_type, ignored)
            self.append_log(f"已更新扩展名 {ext} 分类。")
            self.refresh_stats()
            self.refresh_unknown_extensions()
        except Exception as exc:
            QMessageBox.warning(self, "失败", f"更新扩展名失败：{exc}")
