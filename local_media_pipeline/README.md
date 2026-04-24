# local_media_pipeline

Windows 本地照片/视频整理系统 V1.0（第一阶段骨架版）。

## 目标

- 扫描 `L:\_INBOX_` 文件。
- 初始化 SQLite 数据库（WAL）。
- 增量入库文件基础元数据。
- 提供 PySide6 中文 Dashboard，支持初始化与扫描。

## 环境要求

1. 安装 Python 3.12+
2. 安装依赖：

```bash
pip install -r requirements.txt
```

3. 系统安装 `ffmpeg` 并加入 `PATH`。

## 运行

```bash
python main.py
```

## 首次使用步骤

1. 首次运行点击“初始化数据库”。
2. 把百度网盘文件下载到 `L:\_INBOX_`。
3. 点击“扫描 INBOX”。

## 项目结构

- `app/`：配置、路径、数据库、扫描逻辑。
- `ui/`：主窗口和 Dashboard。
- `scripts/`：命令行初始化与扫描脚本。

## 说明

- 当 `L:` 或 `D:` 不可用时，系统会给出中文错误提示，不会直接崩溃。
- 扫描遵循增量规则：`current_path` 已存在且 `size+mtime` 未变化则跳过。
- 当前阶段不包含 AI、缩略图生成、视频抽帧、全量 hash。
