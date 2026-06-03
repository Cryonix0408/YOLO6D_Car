# 主机数据共享配置

本文档说明如何把主机配置成 YOLO6D_Car 的大数据存储端，并让采集笔记本通过 `Z:\` 访问。

## 目标

- 主机保存大体积数据：`G:\YOLO6D_Car_Data`
- 采集笔记本把主机共享盘映射为：`Z:\`
- 笔记本采集数据先放在：`D:\CaptureData\<session>`
- 回来后同步到：`Z:\captures`
- 主机最终数据位置：`G:\YOLO6D_Car_Data\captures\<date>\<session>`

## 1. 在主机上创建目录

在主机管理员 PowerShell 中运行：

```powershell
New-Item -ItemType Directory -Force -Path G:\YOLO6D_Car_Data
New-Item -ItemType Directory -Force -Path G:\YOLO6D_Car_Data\captures
New-Item -ItemType Directory -Force -Path G:\YOLO6D_Car_Data\FZmotion_Data
New-Item -ItemType Directory -Force -Path G:\YOLO6D_Car_Data\FZmotion_Data\raw_csv
New-Item -ItemType Directory -Force -Path G:\YOLO6D_Car_Data\outputs
New-Item -ItemType Directory -Force -Path G:\YOLO6D_Car_Data\outputs\auto_labels
New-Item -ItemType Directory -Force -Path G:\YOLO6D_Car_Data\outputs\datasets
New-Item -ItemType Directory -Force -Path G:\YOLO6D_Car_Data\outputs\train_runs
New-Item -ItemType Directory -Force -Path G:\YOLO6D_Car_Data\outputs\calibration
New-Item -ItemType Directory -Force -Path G:\YOLO6D_Car_Data\models
New-Item -ItemType Directory -Force -Path G:\YOLO6D_Car_Data\results
New-Item -ItemType Directory -Force -Path G:\YOLO6D_Car_Data\logs
```

也可以用项目脚本检查：

```powershell
D:\Envs\yolo6d\python.exe scripts\check_host_share_ready.py --create
```

## 2. 共享 `G:\YOLO6D_Car_Data`

Windows 图形界面操作：

1. 打开文件资源管理器。
2. 右键 `G:\YOLO6D_Car_Data`。
3. 点击“属性”。
4. 打开“共享”选项卡。
5. 点击“高级共享”。
6. 勾选“共享此文件夹”。
7. 共享名设置为：

```text
YOLO6D_Car_Data
```

8. 点击“权限”。
9. 给同步用户读写或更改权限。
10. 只在可信局域网内临时使用时，可以给 `Everyone` 更改权限。

不要把这个共享暴露到公网。

## 3. 检查主机 IP

在主机上运行：

```powershell
ipconfig
```

找到当前局域网的 IPv4 地址，例如：

```text
192.168.50.250
```

共享路径就是：

```text
\\192.168.50.250\YOLO6D_Car_Data
```

## 4. 在采集笔记本上映射 `Z:\`

推荐用 PowerShell：

```powershell
net use Z: "\\192.168.50.250\YOLO6D_Car_Data" /user:Cryonixzz\yolo_sync <你的密码> /persistent:yes
```

如果之前映射错了，先清理：

```powershell
net use * /delete /y
cmdkey /delete:192.168.50.250
```

映射成功后检查：

```powershell
Test-Path Z:\
dir Z:\
dir Z:\captures
```

## 5. 小文件同步测试

在采集笔记本上创建测试 session：

```powershell
New-Item -ItemType Directory -Force -Path D:\CaptureData\sync_test_001
"hello sync" | Out-File D:\CaptureData\sync_test_001\test.txt
"sample_id,timestamp" | Out-File D:\CaptureData\sync_test_001\capture_index.csv
```

进入项目：

```powershell
cd D:\YOLO6D_Car
```

先扫描：

```powershell
python .\scripts\sync_capture_to_host.py --local-root D:\CaptureData\sync_test_001 --host-root Z:\captures --experiment sync_test_001 --date 2026-05-30 --plan-only
```

正式同步：

```powershell
python .\scripts\sync_capture_to_host.py --local-root D:\CaptureData\sync_test_001 --host-root Z:\captures --experiment sync_test_001 --date 2026-05-30 --verify
```

主机上检查：

```powershell
dir G:\YOLO6D_Car_Data\captures\2026-05-30\sync_test_001
```

应看到：

- `test.txt`
- `capture_index.csv`
- `sync_log.txt`

## 6. 常见故障

笔记本无法访问 `\\<HOST_IP>\YOLO6D_Car_Data`：

- 确认主机 IP 是否正确。
- 确认两台电脑在同一个局域网。
- 在笔记本运行 `ping <HOST_IP>`。
- 确认 Windows 已开启网络发现和文件共享。

`Z:\` 不存在：

- 重新映射网络驱动器。
- 确认主机没有睡眠。
- 重新输入 Windows 凭据。

密码错误：

- 用户名建议写完整：`主机名\用户名`。
- 例如：`Cryonixzz\yolo_sync`。
- 确认该用户在主机上真实存在。

权限拒绝：

- 检查共享权限。
- 检查 NTFS 安全权限。
- 临时测试时可给 `Everyone` 更改权限，确认通路后再收紧。

同步慢：

- 大数据优先用有线网。
- 不要一边训练一边同步。
- 先用 `--plan-only` 看文件数量和总大小。

同步中断：

- 直接重跑同步命令。
- 默认会跳过已经复制成功且大小一致的文件。

## 7. 安全建议

- 共享只在可信局域网使用。
- 不要暴露到公网。
- 不要把 `captures/`、`outputs/`、`models/*.pt` 放进 Git。
- 重要数据同步完成后，主机再做一次备份。

