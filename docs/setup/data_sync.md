# 数据同步流程

本文档说明如何把采集笔记本上的数据同步到主机。代码用 Git 管理，大体积数据不要进 Git，统一通过共享盘或同步脚本传输。

## 使用场景

采集笔记本采完一组数据后，本地通常在：

```text
D:\CaptureData\<session>
```

主机共享盘在笔记本上通常映射为：

```text
Z:\
```

其中：

```text
Z:\captures
```

对应主机真实路径：

```text
G:\YOLO6D_Car_Data\captures
```

## 目标目录结构

同步后的目录结构为：

```text
<host-root>\<date>\<experiment>\<relative-source-path>
```

例如：

```text
Z:\captures\2026-05-30\uav_4m_reshoot_d40_bgA_lightOn
```

主机真实位置为：

```text
G:\YOLO6D_Car_Data\captures\2026-05-30\uav_4m_reshoot_d40_bgA_lightOn
```

默认支持同步的文件类型：

```text
.png .jpg .jpeg .bmp .mp4 .avi .mkv .csv .json .yaml .yml .txt .md
```

## 笔记本同步到主机

在采集笔记本上，进入项目目录：

```powershell
cd D:\YOLO6D_Car
```

先扫描计划，不真正复制：

```powershell
python .\scripts\sync_capture_to_host.py --local-root D:\CaptureData\uav_4m_reshoot_d40_bgA_lightOn --host-root Z:\captures --experiment uav_4m_reshoot_d40_bgA_lightOn --date 2026-05-30 --plan-only
```

正式同步并校验文件大小：

```powershell
python .\scripts\sync_capture_to_host.py --local-root D:\CaptureData\uav_4m_reshoot_d40_bgA_lightOn --host-root Z:\captures --experiment uav_4m_reshoot_d40_bgA_lightOn --date 2026-05-30 --verify
```

默认不会覆盖已有文件。如果目标端已有同名且大小一致的文件，会自动跳过；如果同名但大小不一致，会提示不匹配。

## 批量同步多个 session

如果 `D:\CaptureData` 下有多个 session，可以先扫描：

```powershell
python .\scripts\sync_capture_batch_to_host.py --local-root D:\CaptureData --host-root Z:\captures --plan-only
```

确认无误后正式同步：

```powershell
python .\scripts\sync_capture_batch_to_host.py --local-root D:\CaptureData --host-root Z:\captures --verify
```

说明：

- 默认会跳过 `sync_test_*` 测试目录。
- 如果只想同步某一组，加 `--session <session_name>`。
- 如果要包含测试目录，加 `--include-test`。

## 主机本地直拷

如果你人在主机上运行，并且源目录对主机可见，可以直接写主机真实路径：

```powershell
D:\Envs\yolo6d\python.exe scripts\sync_capture_to_host.py --local-root D:\CaptureData\uav_4m_reshoot_d40_bgA_lightOn --host-root G:\YOLO6D_Car_Data\captures --experiment uav_4m_reshoot_d40_bgA_lightOn --date 2026-05-30 --verify
```

## dry-run、plan-only 和 verify 的区别

`--plan-only`：

- 只扫描源端和目标端。
- 会统计新增文件、重复文件、大小不一致文件。
- 不创建目标目录，不复制文件。

`--dry-run`：

- 会生成目标 session 目录和日志。
- 只打印计划复制哪些文件。
- 不真正复制数据。

`--verify`：

- 正式复制。
- 每个文件复制后检查源文件和目标文件大小是否一致。
- 建议真实同步时始终使用。

## 覆盖模式

默认不覆盖已有文件。如果你确定目标端文件需要替换，才使用：

```powershell
python .\scripts\sync_capture_to_host.py --local-root D:\CaptureData\session --host-root Z:\captures --experiment session --date 2026-05-30 --overwrite --verify
```

谨慎使用 `--overwrite`，避免把主机上已有的正确数据覆盖掉。

## 小文件测试

第一次配置共享盘后，先做小文件测试：

```powershell
New-Item -ItemType Directory -Force -Path D:\CaptureData\sync_test_001
"hello sync" | Out-File D:\CaptureData\sync_test_001\test.txt
"sample_id,timestamp" | Out-File D:\CaptureData\sync_test_001\capture_index.csv
```

扫描：

```powershell
python .\scripts\sync_capture_to_host.py --local-root D:\CaptureData\sync_test_001 --host-root Z:\captures --experiment sync_test_001 --date 2026-05-30 --plan-only
```

正式同步：

```powershell
python .\scripts\sync_capture_to_host.py --local-root D:\CaptureData\sync_test_001 --host-root Z:\captures --experiment sync_test_001 --date 2026-05-30 --verify
```

检查结果：

```powershell
dir Z:\captures\2026-05-30\sync_test_001
```

## 常见问题

`Local source directory does not exist`：

- 本地 session 路径写错。
- 先运行 `dir D:\CaptureData` 确认目录名。

`host-root does not exist`：

- `Z:\captures` 没挂载成功。
- 先运行 `Test-Path Z:\captures`。

没有找到可同步文件：

- 检查文件后缀是否在默认支持列表内。
- 或用 `--extensions png csv json txt` 指定。

权限拒绝：

- 检查主机共享权限。
- 检查主机 NTFS 安全权限。
- 检查是否有程序占用了目标文件。

同步中断：

- 直接重跑同一条命令，不加 `--overwrite`。
- 已复制且大小一致的文件会自动跳过。

