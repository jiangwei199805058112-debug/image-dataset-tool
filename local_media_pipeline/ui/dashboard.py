from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.db import Database
from app.scanner import InboxScanner
from app.services import AppServices
from ui.path_settings_dialog import PathSettingsDialog


class ScanWorker(QObject):
    progress = Signal(dict)
    finished = Signal(dict)

    def __init__(self, services: AppServices):
        super().__init__()
        self.services = services
        self.scanner: InboxScanner | None = None

    @Slot()
    def run(self) -> None:
        thread_db = Database(self.services.paths.database_path)
        thread_db.connect()
        thread_db.init_schema()
        try:
            self.scanner = InboxScanner(
                db=thread_db,
                inbox_root=self.services.paths.inbox_path,
                quick_hash_bytes=65536,
                exclude_roots=[self.services.paths.vault_path, self.services.paths.pipeline_root],
            )
            result = self.scanner.run_scan(progress=self.progress.emit)
            self.finished.emit({"ok": True, "scanned": result.scanned_files, "new": result.new_files, "updated": result.updated_files, "skipped": result.skipped_files, "errors": result.error_files})
        except Exception as exc:
            self.finished.emit({"ok": False, "scanned": 0, "new": 0, "updated": 0, "skipped": 0, "errors": 1, "message": str(exc)})
        finally:
            thread_db.close()
            self.scanner = None

    @Slot()
    def pause(self) -> None:
        if self.scanner:
            self.scanner.pause()

    @Slot()
    def resume(self) -> None:
        if self.scanner:
            self.scanner.resume()

    @Slot()
    def stop(self) -> None:
        if self.scanner:
            self.scanner.stop()


class DashboardPage(QWidget):
    def __init__(self, services: AppServices):
        super().__init__()
        self.services = services
        self.scan_thread: QThread | None = None
        self.scan_worker: ScanWorker | None = None
        self.is_paused = False
        self._build_ui()
        self.refresh_path_labels()
        self.refresh_stats()

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

        scan_box = QGroupBox("扫描控制")
        scan_layout = QVBoxLayout()
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

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        self.scan_stat_label = QLabel("已扫描/新增/更新/跳过/错误：0/0/0/0/0")
        self.current_path_label = QLabel("当前路径：-")

        scan_layout.addLayout(btn_row)
        scan_layout.addWidget(self.progress_bar)
        scan_layout.addWidget(self.scan_stat_label)
        scan_layout.addWidget(self.current_path_label)
        scan_box.setLayout(scan_layout)

        self.log_box = QTextEdit(); self.log_box.setReadOnly(True)

        root.addWidget(path_box)
        root.addWidget(stats_box)
        root.addWidget(scan_box)
        root.addWidget(self.log_box)
        self.setLayout(root)

    def append_log(self, text: str) -> None:
        if text:
            self.log_box.append(text)

    def refresh_path_labels(self) -> None:
        self.db_path_label.setText(str(self.services.paths.database_path))
        self.inbox_path_label.setText(str(self.services.paths.inbox_path))
        self.vault_path_label.setText(str(self.services.paths.vault_path))
        self.pipeline_root_label.setText(str(self.services.paths.pipeline_root))

    def open_path_settings(self) -> None:
        dialog = PathSettingsDialog(self.services, self)
        if dialog.exec():
            self.refresh_path_labels()
            self.refresh_stats()

    def on_init_db(self) -> None:
        ok, message = self.services.initialize_database()
        self.append_log(message)
        if not ok:
            QMessageBox.warning(self, "初始化失败", message)
        self.refresh_stats()

    def on_scan(self) -> None:
        if not self.services.has_required_paths() or not self.services.paths.inbox_path.exists():
            QMessageBox.warning(self, "提示", "INBOX 路径不存在，请先设置路径。")
            return
        self.scan_btn.setEnabled(False)
        self.pause_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)
        self.is_paused = False
        self.pause_btn.setText("暂停扫描")
        self.progress_bar.setVisible(True)

        self.scan_thread = QThread(self)
        self.scan_worker = ScanWorker(self.services)
        self.scan_worker.moveToThread(self.scan_thread)
        self.scan_thread.started.connect(self.scan_worker.run)
        self.scan_worker.progress.connect(self.on_scan_progress)
        self.scan_worker.finished.connect(self.on_scan_finished)
        self.scan_worker.finished.connect(self.scan_thread.quit)
        self.scan_thread.finished.connect(self.cleanup_scan_thread)
        self.scan_thread.start()

    def on_pause_resume(self) -> None:
        if not self.scan_worker:
            return
        if not self.is_paused:
            self.scan_worker.pause()
            self.is_paused = True
            self.pause_btn.setText("继续扫描")
        else:
            self.scan_worker.resume()
            self.is_paused = False
            self.pause_btn.setText("暂停扫描")

    def on_stop(self) -> None:
        if self.scan_worker:
            self.scan_worker.stop()
        self.scan_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.pause_btn.setText("暂停扫描")

    def on_scan_progress(self, payload: dict) -> None:
        self.scan_stat_label.setText(
            f"已扫描/新增/更新/跳过/错误：{payload.get('scanned_files',0)}/{payload.get('new_files',0)}/{payload.get('updated_files',0)}/{payload.get('skipped_files',0)}/{payload.get('error_files',0)}"
        )
        self.current_path_label.setText(f"当前路径：{payload.get('current_path','-')}")
        msg = payload.get("message", "")
        if msg:
            self.append_log(msg)

        t = payload.get("type_counts", {})
        if t:
            self.image_label.setText(str(t.get("image", 0)))
            self.raw_label.setText(str(t.get("raw_image", 0)))
            self.video_label.setText(str(t.get("video", 0)))
            self.document_label.setText(str(t.get("document", 0)))
            self.archive_label.setText(str(t.get("archive", 0)))
            self.software_label.setText(str(t.get("software", 0)))
            self.audio_label.setText(str(t.get("audio", 0)))
            self.other_label.setText(str(t.get("other", 0)))

    def on_scan_finished(self, payload: dict) -> None:
        if not payload.get("ok", False):
            self.append_log(f"扫描失败：{payload.get('message','')} ")
        self.scan_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.pause_btn.setText("暂停扫描")
        self.progress_bar.setVisible(False)
        self.refresh_stats()

    def cleanup_scan_thread(self) -> None:
        self.scan_worker = None
        self.scan_thread = None

    def refresh_stats(self) -> None:
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
