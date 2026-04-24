from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from app.services import AppServices


class PathSettingsDialog(QDialog):
    def __init__(self, services: AppServices, parent=None):
        super().__init__(parent)
        self.services = services
        self.setWindowTitle("路径设置")
        self.resize(760, 300)
        self._build_ui()
        self._load_values()

    def _build_ui(self) -> None:
        root = QVBoxLayout()
        form = QFormLayout()

        self.inbox_edit = QLineEdit()
        self.vault_edit = QLineEdit()
        self.pipeline_edit = QLineEdit()
        self.batch_size_spin = QSpinBox()
        self.batch_size_spin.setRange(1, 4096)
        self.single_copy_check = QCheckBox("单副本安全移动模式（节省硬盘空间）")

        form.addRow("INBOX 路径", self._row(self.inbox_edit, self._pick_inbox))
        form.addRow("VAULT 路径", self._row(self.vault_edit, self._pick_vault))
        form.addRow("PIPELINE_ROOT", self._row(self.pipeline_edit, self._pick_pipeline))
        form.addRow("batch_size_gb", self.batch_size_spin)
        form.addRow("模式", self.single_copy_check)

        save_btn = QPushButton("保存")
        cancel_btn = QPushButton("取消")
        save_btn.clicked.connect(self._save)
        cancel_btn.clicked.connect(self.reject)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(save_btn)
        buttons.addWidget(cancel_btn)

        root.addLayout(form)
        root.addLayout(buttons)
        self.setLayout(root)

    def _row(self, edit: QLineEdit, picker) -> QHBoxLayout:
        btn = QPushButton("选择...")
        btn.clicked.connect(picker)
        row = QHBoxLayout()
        row.addWidget(edit)
        row.addWidget(btn)
        return row

    def _load_values(self) -> None:
        self.inbox_edit.setText(self.services.config.get("inbox_path", ""))
        self.vault_edit.setText(self.services.config.get("vault_path", ""))
        self.pipeline_edit.setText(self.services.config.get("pipeline_root", ""))
        self.batch_size_spin.setValue(int(self.services.config.get("batch_size_gb", 100)))
        self.single_copy_check.setChecked(bool(self.services.config.get("single_copy_mode", False)))

    def _pick_folder(self, edit: QLineEdit) -> None:
        current = edit.text().strip()
        picked = QFileDialog.getExistingDirectory(self, "选择文件夹", current or str(Path.home()))
        if picked:
            edit.setText(picked)

    def _pick_inbox(self) -> None:
        self._pick_folder(self.inbox_edit)

    def _pick_vault(self) -> None:
        self._pick_folder(self.vault_edit)

    def _pick_pipeline(self) -> None:
        self._pick_folder(self.pipeline_edit)

    def _save(self) -> None:
        inbox = self.inbox_edit.text().strip()
        vault = self.vault_edit.text().strip()
        pipeline = self.pipeline_edit.text().strip()
        if not inbox or not vault or not pipeline:
            QMessageBox.warning(self, "提示", "请完整设置三个路径后再保存。")
            return

        new_mode = self.single_copy_check.isChecked()
        old_mode = bool(self.services.config.get("single_copy_mode", False))
        if new_mode and not old_mode:
            text = "处理批次时，文件会从 INBOX 安全移动到 SSD，校验成功后 INBOX 原文件会被删除。是否确认启用？"
            answer = QMessageBox.question(self, "确认启用单副本模式", text)
            if answer != QMessageBox.StandardButton.Yes:
                return

        ok, message = self.services.save_paths_config(
            inbox_path=inbox,
            vault_path=vault,
            pipeline_root=pipeline,
            batch_size_gb=int(self.batch_size_spin.value()),
            single_copy_mode=new_mode,
        )
        if not ok:
            QMessageBox.critical(self, "保存失败", message)
            return

        QMessageBox.information(self, "成功", message)
        self.accept()
