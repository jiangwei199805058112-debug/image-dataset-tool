# local_media_pipeline

Windows 本地照片/视频整理系统 V1.0。

## 扫描能力（增强版）

- 支持**暂停 / 继续 / 停止**扫描。
- 停止后可续扫；续扫采用**增量扫描**（按 `current_path + file_size + mtime` 快速跳过未变化文件），不会重复入库。
- 扫描过程只读 INBOX：不会移动、删除、重命名文件；不生成缩略图、不抽视频帧、不跑 AI、不计算 full_hash。

## 文件类型统计与未知扩展名发现

- Dashboard 基于 SQLite `files` 表统计：
  - 总数、image、raw_image、video、document、archive、software、audio、other、ERROR、ARCHIVED。
- RAW 默认支持：`.arw .raw .cr2 .cr3 .nef .raf .dng .orf .rw2 .srw .pef .x3f`。
- 扫描会更新 `extension_stats`，自动发现未知扩展名。
- 未知扩展名超过阈值（默认 10）会提示用户确认分类。
- 用户确认后写入 `confirmed_type`，后续扫描按该类型归类，并批量修正已入库文件类型。

## 单副本安全移动模式

- 普通复制模式（`single_copy_mode=false`）：提取批次到 PROCESSING 时**不会删除 INBOX 源文件**。
- 单副本安全移动模式（`single_copy_mode=true`）：校验成功后删除 INBOX 源文件，节省空间。
- 归档时也采用安全移动：仅在校验通过后删除 SSD 源文件。

## 配置文件

`config.json`：

```json
{
  "inbox_path": "",
  "vault_path": "",
  "pipeline_root": "",
  "batch_size_gb": 100,
  "single_copy_mode": false,
  "gap_mode": "NORMAL",
  "snooze_days": 7
}
```

## 运行

```bash
pip install -r requirements.txt
python main.py
```

## 8TB 扫描性能规则

- 扫描采用流式遍历（`os.walk`），边遍历边写 SQLite，不会一次性加载全量路径。
- 已入库且 `file_size + mtime` 未变化的文件会快速跳过，不重算 quick_hash、不重复累计扩展名统计。
- 不使用 `ProcessPoolExecutor` 或大并发随机读盘。
- UI 进度按批次（默认每 500 个文件）刷新，不做每文件刷新。
- `quick_hash` 只读前 64KB；`full_hash` 仅在 SSD 批处理阶段按分块读取。
- 不使用 tqdm；通过 PySide6 signal 刷新日志与进度。
