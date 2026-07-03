# scripts/sync 目录说明

`scripts/sync/` 用于未来放主机 / 笔记本数据同步、共享盘检查、批量传输等脚本。

未来候选包括：

- `sync_capture_to_host.py`
- `sync_capture_batch_to_host.py`
- `check_host_share_ready.py`

本轮 Phase C2 不移动这些旧脚本。后续迁移前必须保证旧命令兼容，例如先保留根目录 wrapper，或同步更新 README、docs 和实验命令。
