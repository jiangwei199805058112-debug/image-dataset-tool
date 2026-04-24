# local_media_pipeline

Windows 本地照片/视频整理系统 V1.0（第一阶段骨架版）。

## 目标

- 扫描用户自定义 `INBOX` 文件夹。
- 初始化 SQLite 数据库（WAL）。
- 增量入库文件基础元数据。
- 提供 PySide6 中文 Dashboard，支持路径设置、初始化与扫描。

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

1. 启动程序后点击“设置路径”。
2. 选择并保存：
   - `INBOX 路径`
   - `VAULT 路径`
   - `PIPELINE_ROOT`
3. 点击“初始化数据库”。
4. 点击“扫描 INBOX”。

## 路径说明

- 路径全部来自 `config.json`。
- 路径可以自由修改，不依赖固定盘符。
- 保存路径时会自动创建以下目录（如不存在）：
  - `PIPELINE_ROOT/SYSTEM`
  - `PIPELINE_ROOT/02_PROCESSING`
  - `PIPELINE_ROOT/03_UNCERTAIN`
  - `PIPELINE_ROOT/04_REVIEWED`
  - `PIPELINE_ROOT/05_TO_DELETE`
  - `PIPELINE_ROOT/06_READY_TO_ARCHIVE`
  - `PIPELINE_ROOT/TEMP/preview_cache`

## 项目结构

- `app/`：配置、路径、数据库、扫描逻辑。
- `ui/`：主窗口、Dashboard、路径设置弹窗。
- `scripts/`：命令行初始化与扫描脚本。

## 说明

- 如果 `inbox_path` 为空或不存在，程序启动会提示“请先设置路径”并自动打开设置窗口。
- 路径相关操作做了异常捕获并写入日志，避免程序崩溃。
- 当前阶段不包含 AI、缩略图生成、视频抽帧、全量 hash。
