# 采集笔记本实验室采集流程

本文档用于采集笔记本。原则是：实验室采集先写入 `D:\CaptureData`，回到主机网络环境后再同步到 `Z:\captures`。

## 当前脚本状态

| 功能 | 脚本 | 状态 | 输出建议 |
|---|---|---|---|
| 海康工业相机连续帧采集 | `scripts\collect_hikvision_sequence.py` | 可用 | `D:\CaptureData\<session>` |
| 海康相机实时预览测试 | `scripts\test_hikvision_camera.py` | 可用 | 不保存或只预览 |
| D455/webcam 自动采集 | `scripts\capture_object_samples.py` | 可用 | `D:\CaptureData\<session>` |
| Hikrobot 自动保存逻辑 | `scripts\capture_object_samples.py` | 未实现实时海康后端 | 海康请用连续帧采集脚本 |
| 采集质量检查 | `scripts\check_capture_quality.py` | 可用 | `D:\CaptureData\results\capture_quality\<session>` |
| FzMotion CSV 检查 | `scripts\check_mocap_csv.py` | 可用 | 只检查，不修改 CSV |
| 批量同步到主机 | `scripts\sync_capture_batch_to_host.py` | 可用 | `Z:\captures` |

## 明天采集前检查

在笔记本 PowerShell 中进入项目：

```powershell
Set-Location D:\YOLO6D_Car
```

检查笔记本路径配置：

```powershell
python .\scripts\capture_object_samples.py --config .\configs\object_capture_auto.yaml --paths-config .\configs\paths_laptop.yaml --validate-config
```

检查主机共享盘是否在线。实验室没连主机网络时，这一步可以跳过：

```powershell
Test-Path Z:\
Test-Path Z:\captures
```

## 海康相机预览

先只看画面，不采集：

```powershell
python .\scripts\test_hikvision_camera.py --mvs-python-path "E:\MVS\Development\Samples\Python\MvImport" --frame-rate 60 --exposure-time-us 5000 --gain-db 6 --preview-gain 3 --preview-gamma 1.6
```

如果画面太暗，优先加灯，再小幅提高曝光或增益。快速运动建议曝光尽量短，例如 `3000` 到 `6000 us`。

## 海康连续帧采集

新建 session 名时建议包含日期、目标、速度、方向、编号，例如：

```text
2026-06-04_hik_fast_lateral_001
2026-06-04_hik_slow_nearfar_001
2026-06-04_hik_occlusion_001
```

正式采集命令示例：

```powershell
python .\scripts\collect_hikvision_sequence.py --output-dir "D:\CaptureData\2026-06-04_hik_fast_lateral_001" --duration 20 --fps 60 --exposure-us 5000 --gain 6 --width 1440 --height 1080 --mvs-python-path "E:\MVS\Development\Samples\Python\MvImport" --preview --preview-before-start --preview-gain 3 --preview-gamma 1.6
```

输出结构：

```text
D:\CaptureData\<session>
├── images
├── camera_timestamps.csv
└── config.yaml
```

## D455 或 webcam 自动采集

自动采集脚本会根据清晰度、稳定性和画面变化自动保存。为了让数据直接落到 `D:\CaptureData\<session>`，建议显式指定 `--output-dir`：

```powershell
python .\scripts\capture_object_samples.py --config .\configs\object_capture_auto.yaml --paths-config .\configs\paths_laptop.yaml --output-dir "D:\CaptureData\2026-06-04_car_static_001"
```

说明：当前这个脚本的 Hikrobot 实时后端未实现。海康工业相机请优先用 `collect_hikvision_sequence.py`。

## 采集后质量检查

检查某个 session 的图像质量：

```powershell
python .\scripts\check_capture_quality.py --capture-root "D:\CaptureData\2026-06-04_hik_fast_lateral_001" --output-dir "D:\CaptureData\results\capture_quality\2026-06-04_hik_fast_lateral_001" --plot
```

重点看：

- 图片数量是否符合预期。
- 分辨率是否一致。
- 损坏图片是否为 0。
- blur score 是否明显过低。
- 是否有大量过于相似的连续帧。

## FzMotion CSV 放置

采集完后把对应 CSV 放到：

```text
D:\CaptureData\FZmotion_Data\<session>.csv
```

如果 CSV 暂时还在 FzMotion 默认目录，也可以先不移动，但同步前建议统一放到 `D:\CaptureData\FZmotion_Data`。

## 回来后同步到主机

确认主机共享盘：

```powershell
Test-Path Z:\
Test-Path Z:\captures
```

先扫描，不复制：

```powershell
python .\scripts\sync_capture_batch_to_host.py --local-root D:\CaptureData --host-root Z:\captures --plan-only
```

确认 `size_mismatch_files=0` 后正式同步：

```powershell
python .\scripts\sync_capture_batch_to_host.py --local-root D:\CaptureData --host-root Z:\captures --verify
```

如果只同步一个 session：

```powershell
python .\scripts\sync_capture_batch_to_host.py --local-root D:\CaptureData --host-root Z:\captures --session 2026-06-04_hik_fast_lateral_001 --plan-only
python .\scripts\sync_capture_batch_to_host.py --local-root D:\CaptureData --host-root Z:\captures --session 2026-06-04_hik_fast_lateral_001 --verify
```

## 实验室现场建议

- 每组采集前先预览，确认小车在画面内、曝光不过暗、运动不糊。
- 快速运动优先保证短曝光和补光，不要只靠高增益。
- 每个 session 只做一种运动条件，例如 lateral、nearfar、diagonal、occlusion。
- 每个 session 结束后立刻检查 `images` 数量和 `camera_timestamps.csv` 是否存在。
- 不要把新采集数据放进 Git；数据走 `D:\CaptureData` 到 `Z:\captures`。
