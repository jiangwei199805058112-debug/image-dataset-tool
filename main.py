import os
import sys
import shutil
from typing import Optional

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import (
    QDragEnterEvent,
    QDropEvent,
    QKeySequence,
    QPixmap,
    QShortcut,
)
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from send2trash import send2trash


class ThumbnailLabel(QLabel):
    def __init__(self, index: int, viewer: "ImageViewer"):
        super().__init__()
        self.index = index
        self.viewer = viewer
        self.setFixedSize(150, 100)
        self.setAlignment(Qt.AlignCenter)
        self.setFrameShape(QFrame.Box)
        self.setLineWidth(2)
        self.setStyleSheet("background:#2b2b2b; border:2px solid #555;")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.viewer.jump_to_image(self.index)
        super().mousePressEvent(event)


class ImageViewer(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("图片整理器")
        self.resize(1650, 980)
        self.setAcceptDrops(True)
        self.setFocusPolicy(Qt.StrongFocus)

        self.image_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
        self.image_paths: list[str] = []
        self.current_index = -1
        self.current_folder: Optional[str] = None

        self.delete_history: list[dict[str, str]] = []
        self.undo_limit = 5

        self.target_dirs: dict[int, Optional[str]] = {
            1: None,
            2: None,
            3: None,
        }

        self.undo_dir = self.normalize_path(os.path.join(os.getcwd(), ".undo_temp"))
        os.makedirs(self.undo_dir, exist_ok=True)

        # 只显示当前附近缩略图，避免一次性载入过多导致卡顿
        self.thumb_radius = 5

        self.build_ui()
        self.bind_shortcuts()
        self.update_target_labels()

    def normalize_path(self, path: str) -> str:
        return os.path.abspath(os.path.normpath(path))

    def build_ui(self):
        self.setStyleSheet(
            """
            QWidget {
                background: #1e1e1e;
                color: #e6e6e6;
                font-size: 14px;
            }

            QPushButton {
                background: #333333;
                border: 1px solid #555;
                padding: 8px 14px;
                min-height: 34px;
            }

            QPushButton:hover {
                background: #444444;
            }

            QLabel#infoLabel {
                color: #cfcfcf;
                padding: 4px 0;
            }

            QLabel#pathLabel {
                color: #bdbdbd;
                padding: 2px 0;
            }

            QLabel#imageLabel {
                background: #2a2a2a;
                border: 1px solid #4a4a4a;
            }

            QScrollArea {
                border: 1px solid #444;
                background: #242424;
            }
            """
        )

        root = QVBoxLayout()
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        self.open_button = QPushButton("打开文件夹")
        self.open_button.clicked.connect(self.open_folder)

        self.btn_set_1 = QPushButton("设置1号文件夹")
        self.btn_set_1.clicked.connect(lambda: self.set_target_dir(1))

        self.btn_set_2 = QPushButton("设置2号文件夹")
        self.btn_set_2.clicked.connect(lambda: self.set_target_dir(2))

        self.btn_set_3 = QPushButton("设置3号文件夹")
        self.btn_set_3.clicked.connect(lambda: self.set_target_dir(3))

        self.folder_label = QLabel("当前文件夹：未打开")
        self.folder_label.setObjectName("infoLabel")

        top_bar.addWidget(self.open_button)
        top_bar.addWidget(self.btn_set_1)
        top_bar.addWidget(self.btn_set_2)
        top_bar.addWidget(self.btn_set_3)
        top_bar.addWidget(self.folder_label, 1)

        self.target_label_1 = QLabel()
        self.target_label_1.setObjectName("pathLabel")

        self.target_label_2 = QLabel()
        self.target_label_2.setObjectName("pathLabel")

        self.target_label_3 = QLabel()
        self.target_label_3.setObjectName("pathLabel")

        self.info_label = QLabel("请点击按钮选择文件夹，或直接把文件夹拖进窗口")
        self.info_label.setObjectName("infoLabel")
        self.info_label.setAlignment(Qt.AlignCenter)

        self.image_label = QLabel("这里显示大图")
        self.image_label.setObjectName("imageLabel")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(1000, 650)

        self.thumb_title = QLabel("缩略图")
        self.thumb_title.setObjectName("infoLabel")

        self.thumbnail_container = QWidget()
        self.thumbnail_layout = QHBoxLayout()
        self.thumbnail_layout.setContentsMargins(10, 10, 10, 10)
        self.thumbnail_layout.setSpacing(8)
        self.thumbnail_container.setLayout(self.thumbnail_layout)

        self.thumbnail_scroll = QScrollArea()
        self.thumbnail_scroll.setWidgetResizable(True)
        self.thumbnail_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.thumbnail_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.thumbnail_scroll.setFixedHeight(145)
        self.thumbnail_scroll.setWidget(self.thumbnail_container)

        root.addLayout(top_bar)
        root.addWidget(self.target_label_1)
        root.addWidget(self.target_label_2)
        root.addWidget(self.target_label_3)
        root.addWidget(self.info_label)
        root.addWidget(self.image_label, 1)
        root.addWidget(self.thumb_title)
        root.addWidget(self.thumbnail_scroll)

        self.setLayout(root)

    def bind_shortcuts(self):
        self.undo_shortcut = QShortcut(QKeySequence("Ctrl+Z"), self)
        self.undo_shortcut.activated.connect(self.undo_delete)

    def update_target_labels(self):
        self.target_label_1.setText(
            f"1号文件夹：{self.target_dirs[1] if self.target_dirs[1] else '未设置'}"
        )
        self.target_label_2.setText(
            f"2号文件夹：{self.target_dirs[2] if self.target_dirs[2] else '未设置'}"
        )
        self.target_label_3.setText(
            f"3号文件夹：{self.target_dirs[3] if self.target_dirs[3] else '未设置'}"
        )

    def set_target_dir(self, idx: int):
        folder = QFileDialog.getExistingDirectory(self, f"选择{idx}号目标文件夹")
        if not folder:
            return

        folder = self.normalize_path(folder)
        self.target_dirs[idx] = folder
        self.update_target_labels()
        self.info_label.setText(f"{idx}号文件夹已设置：{folder}")
        self.setFocus()

    def dragEnterEvent(self, event: QDragEnterEvent):
        mime = event.mimeData()
        if not mime.hasUrls():
            event.ignore()
            return

        for url in mime.urls():
            local_path = self.normalize_path(url.toLocalFile())
            if local_path and os.path.isdir(local_path):
                event.acceptProposedAction()
                return

        event.ignore()

    def dropEvent(self, event: QDropEvent):
        mime = event.mimeData()
        if not mime.hasUrls():
            event.ignore()
            return

        for url in mime.urls():
            local_path = self.normalize_path(url.toLocalFile())
            if local_path and os.path.isdir(local_path):
                self.load_folder(local_path)
                event.acceptProposedAction()
                return

        event.ignore()

    def open_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择图片文件夹")
        if folder:
            folder = self.normalize_path(folder)
            self.load_folder(folder)

    def load_folder(self, folder: str):
        folder = self.normalize_path(folder)

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self.info_label.setText("正在读取文件夹，请稍等...")
            QApplication.processEvents()

            image_paths = []
            with os.scandir(folder) as it:
                for entry in it:
                    if not entry.is_file():
                        continue

                    ext = os.path.splitext(entry.name)[1].lower()
                    if ext in self.image_extensions:
                        image_paths.append(self.normalize_path(entry.path))

            image_paths.sort()

            self.current_folder = folder
            self.folder_label.setText(f"当前文件夹：{folder}")

            if not image_paths:
                self.image_paths = []
                self.current_index = -1
                self.image_label.setPixmap(QPixmap())
                self.image_label.setText("这个文件夹里没有图片")
                self.info_label.setText("没有找到图片")
                self.clear_thumbnails()
                return

            self.image_paths = image_paths
            self.current_index = 0

            self.show_current_image()
            self.rebuild_visible_thumbnails()

        except Exception as e:
            QMessageBox.critical(self, "错误", f"打开文件夹失败：{e}")
        finally:
            QApplication.restoreOverrideCursor()

    def clear_thumbnails(self):
        while self.thumbnail_layout.count():
            item = self.thumbnail_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def rebuild_visible_thumbnails(self):
        self.clear_thumbnails()

        if not self.image_paths or self.current_index < 0:
            return

        start = max(0, self.current_index - self.thumb_radius)
        end = min(len(self.image_paths), self.current_index + self.thumb_radius + 1)

        for i in range(start, end):
            image_path = self.image_paths[i]
            thumb = ThumbnailLabel(i, self)

            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    QSize(146, 96),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
                thumb.setPixmap(scaled)
            else:
                thumb.setText("加载失败")

            if i == self.current_index:
                thumb.setStyleSheet("background:#2b2b2b; border:3px solid #00a8ff;")
            else:
                thumb.setStyleSheet("background:#2b2b2b; border:2px solid #555;")

            self.thumbnail_layout.addWidget(thumb)

        self.thumbnail_layout.addStretch(1)

    def show_current_image(self):
        if not self.image_paths or self.current_index < 0:
            return

        image_path = self.image_paths[self.current_index]
        pixmap = QPixmap(image_path)

        if pixmap.isNull():
            self.image_label.setPixmap(QPixmap())
            self.image_label.setText("图片加载失败")
            self.info_label.setText(f"加载失败：{image_path}")
            return

        scaled = pixmap.scaled(
            self.image_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )

        self.image_label.setPixmap(scaled)
        self.image_label.setText("")
        self.info_label.setText(
            f"{self.current_index + 1} / {len(self.image_paths)}    {os.path.basename(image_path)}"
        )

    def jump_to_image(self, index: int):
        if 0 <= index < len(self.image_paths):
            self.current_index = index
            self.show_current_image()
            self.rebuild_visible_thumbnails()
            self.setFocus()

    def show_prev_image(self):
        if not self.image_paths:
            return
        if self.current_index > 0:
            self.current_index -= 1
            self.show_current_image()
            self.rebuild_visible_thumbnails()

    def show_next_image(self):
        if not self.image_paths:
            return
        if self.current_index < len(self.image_paths) - 1:
            self.current_index += 1
            self.show_current_image()
            self.rebuild_visible_thumbnails()

    def delete_current_image(self):
        if not self.image_paths or self.current_index < 0:
            return

        current_path = self.normalize_path(self.image_paths[self.current_index])

        if not os.path.exists(current_path):
            QMessageBox.warning(self, "提示", "当前文件不存在，无法删除。")
            return

        try:
            backup_name = self.make_unique_backup_name(current_path)
            backup_path = self.normalize_path(os.path.join(self.undo_dir, backup_name))

            shutil.copy2(current_path, backup_path)
            send2trash(current_path)

        except Exception as e:
            QMessageBox.critical(self, "错误", f"删除失败：{e}")
            return

        self.delete_history.append(
            {
                "original_path": current_path,
                "backup_path": backup_path,
            }
        )

        while len(self.delete_history) > self.undo_limit:
            old_record = self.delete_history.pop(0)
            self.safe_remove_backup(old_record["backup_path"])

        del self.image_paths[self.current_index]

        if not self.image_paths:
            self.current_index = -1
            self.image_label.setPixmap(QPixmap())
            self.image_label.setText("没有图片了")
            self.info_label.setText("已全部删除")
            self.clear_thumbnails()
            return

        if self.current_index >= len(self.image_paths):
            self.current_index = len(self.image_paths) - 1

        self.show_current_image()
        self.rebuild_visible_thumbnails()

    def undo_delete(self):
        if not self.delete_history:
            self.info_label.setText("没有可撤回的删除记录")
            return

        record = self.delete_history.pop()
        original_path = self.normalize_path(record["original_path"])
        backup_path = self.normalize_path(record["backup_path"])

        if not os.path.exists(backup_path):
            QMessageBox.warning(self, "提示", "撤回失败：备份文件不存在。")
            return

        try:
            original_dir = self.normalize_path(os.path.dirname(original_path))
            os.makedirs(original_dir, exist_ok=True)

            restore_path = self.make_unique_restore_path(original_path)
            restore_path = self.normalize_path(restore_path)
            shutil.copy2(backup_path, restore_path)

        except Exception as e:
            QMessageBox.critical(self, "错误", f"撤回失败：{e}")
            return

        self.safe_remove_backup(backup_path)

        if self.current_folder and self.normalize_path(os.path.dirname(restore_path)) == self.current_folder:
            self.image_paths.append(self.normalize_path(restore_path))
            self.image_paths.sort()
            self.current_index = self.image_paths.index(self.normalize_path(restore_path))
            self.show_current_image()
            self.rebuild_visible_thumbnails()
        else:
            self.info_label.setText(f"已撤回删除：{restore_path}")

    def move_current_to(self, idx: int):
        if not self.image_paths or self.current_index < 0:
            return

        target_dir = self.target_dirs.get(idx)
        if not target_dir:
            QMessageBox.warning(self, "提示", f"{idx}号文件夹还没设置")
            return

        target_dir = self.normalize_path(target_dir)
        src_path = self.normalize_path(self.image_paths[self.current_index])

        if not os.path.exists(src_path):
            QMessageBox.warning(self, "提示", "当前文件不存在，无法移动。")
            return

        if not os.path.isdir(target_dir):
            QMessageBox.warning(self, "提示", f"{idx}号文件夹不存在")
            return

        filename = os.path.basename(src_path)
        dst_path = self.normalize_path(os.path.join(target_dir, filename))

        base, ext = os.path.splitext(filename)
        counter = 1
        while os.path.exists(dst_path):
            dst_path = self.normalize_path(os.path.join(target_dir, f"{base}_{counter}{ext}"))
            counter += 1

        try:
            shutil.move(src_path, dst_path)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"移动失败：{e}")
            return

        del self.image_paths[self.current_index]

        if not self.image_paths:
            self.current_index = -1
            self.image_label.setPixmap(QPixmap())
            self.image_label.setText("没有图片了")
            self.info_label.setText(f"已移动到 {idx}号文件夹，当前文件夹已处理完成")
            self.clear_thumbnails()
            return

        if self.current_index >= len(self.image_paths):
            self.current_index = len(self.image_paths) - 1

        self.info_label.setText(f"已移动到 {idx}号文件夹：{os.path.basename(dst_path)}")
        self.show_current_image()
        self.rebuild_visible_thumbnails()

    def make_unique_backup_name(self, original_path: str) -> str:
        base_name = os.path.basename(original_path)
        name, ext = os.path.splitext(base_name)

        counter = 0
        while True:
            candidate = f"{name}{ext}" if counter == 0 else f"{name}_{counter}{ext}"
            candidate_path = self.normalize_path(os.path.join(self.undo_dir, candidate))
            if not os.path.exists(candidate_path):
                return candidate
            counter += 1

    def make_unique_restore_path(self, original_path: str) -> str:
        original_path = self.normalize_path(original_path)

        if not os.path.exists(original_path):
            return original_path

        folder = self.normalize_path(os.path.dirname(original_path))
        filename = os.path.basename(original_path)
        name, ext = os.path.splitext(filename)

        counter = 1
        while True:
            candidate = self.normalize_path(os.path.join(folder, f"{name}_restored_{counter}{ext}"))
            if not os.path.exists(candidate):
                return candidate
            counter += 1

    def safe_remove_backup(self, backup_path: str):
        try:
            backup_path = self.normalize_path(backup_path)
            if os.path.exists(backup_path):
                os.remove(backup_path)
        except Exception:
            pass

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_A:
            self.show_prev_image()
            return

        if event.key() == Qt.Key_D:
            self.show_next_image()
            return

        if event.key() == Qt.Key_X:
            self.delete_current_image()
            return

        if event.key() == Qt.Key_1:
            self.move_current_to(1)
            return

        if event.key() == Qt.Key_2:
            self.move_current_to(2)
            return

        if event.key() == Qt.Key_3:
            self.move_current_to(3)
            return

        super().keyPressEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.image_paths and self.current_index >= 0:
            self.show_current_image()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ImageViewer()
    window.show()
    sys.exit(app.exec())