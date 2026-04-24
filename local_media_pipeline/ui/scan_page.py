from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class ScanPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        layout.addWidget(QLabel("扫描页面（V1 占位）"))
        self.setLayout(layout)
