from __future__ import annotations

from PySide6.QtWidgets import QMainWindow, QTabWidget

from app.services import AppServices
from ui.batch_page import BatchPage
from ui.dashboard import DashboardPage
from ui.review_page import ReviewPage
from ui.scan_page import ScanPage


class MainWindow(QMainWindow):
    def __init__(self, services: AppServices):
        super().__init__()
        self.services = services
        self.setWindowTitle("本地媒体整理流水线 V1.0")
        self.resize(980, 720)

        tabs = QTabWidget()
        self.dashboard = DashboardPage(services)
        tabs.addTab(self.dashboard, "总览")
        tabs.addTab(ScanPage(), "扫描")
        tabs.addTab(BatchPage(services), "批次")
        tabs.addTab(ReviewPage(), "复核")

        self.setCentralWidget(tabs)
