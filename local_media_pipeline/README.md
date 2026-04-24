# local_media_pipeline

Windows 本地照片/视频整理系统 V1.0（单副本安全移动策略）。

## 数据流策略

文件生命周期：`INBOX -> 02_PROCESSING -> VAULT`

### 两种模式

1. **普通复制模式**（`single_copy_mode=false`）
   - 进入批次时仅复制到 SSD，不删除 INBOX 源文件。
   - 更安全，但会占用双倍空间。

2. **单副本安全移动模式**（`single_copy_mode=true`）
   - 进入批次时执行“复制 -> 校验 -> 删除源文件”。
   - 仅在校验成功后才删除 INBOX 源文件，节省硬盘空间。
   - 推荐 8TB 空间紧张时启用。

## 关键保证

- 扫描阶段只读，不删除 INBOX 文件。
- 只有进入批次处理且校验成功后，才删除 INBOX 原文件（仅单副本模式）。
- 归档成功并校验通过后，才删除 SSD 源文件。
- 任何失败都会保留源文件，并写入日志。

## 配置（config.json）

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

## 首次使用步骤

1. 启动程序后点击“设置路径”。
2. 选择并保存：INBOX、VAULT、PIPELINE_ROOT。
3. 可选：启用“单副本安全移动模式（节省硬盘空间）”。
4. 点击“初始化数据库”。
5. 点击“扫描 INBOX”。
6. 在“批次”页面执行“提取批次到 PROCESSING”与“归档 READY_TO_ARCHIVE”。

## SSD 安全限制

- `batch_size_gb` 从配置读取，默认 100GB。
- 提取批次时，系统会检查 SSD 可用空间。
- 批次大小不得超过可用空间的 60%。
- 空间不足时会提示：
  `SSD 可用空间不足，请减小批次大小或清理工作区。`

## 运行

```bash
pip install -r requirements.txt
python main.py
```
