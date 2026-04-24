from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class BatchPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        layout.addWidget(QLabel("批次页面（V1 占位）"))
        self.setLayout(layout)
