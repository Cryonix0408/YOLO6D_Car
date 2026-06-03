# 实验日检查清单流程

本文档用于实验当天快速确认：硬件、路径、采集、同步、质检是否都准备好。

## 实验前检查

确认硬件：

- 海康 MV-CS016-10UC
- 对应镜头，例如 8mm
- USB3.0 数据线
- 小车和电池
- 动捕球
- FzMotion 系统
- 采集笔记本电源
- 主机共享盘 `Z:\` 可访问

确认路径：

```powershell
Test-Path D:\YOLO6D_Car
Test-Path D:\CaptureData
Test-Path Z:\captures
```

确认项目：

```powershell
cd D:\YOLO6D_Car
git status
```

## 相机预览

先不采集，只看画面：

```powershell
python .\scripts\test_hikvision_camera.py --mvs-python-path "E:\MVS\Development\Samples\Python\MvImport" --frame-rate 60 --exposure-time-us 5000 --gain-db 6
```

检查：

- 画面亮度
- 噪点
- 视野范围
- 焦点
- 帧率

## 采集 session

示例：

```powershell
python .\scripts\collect_hikvision_sequence.py --output-dir D:\CaptureData\2026-XX-XX_car_fast_lateral_001 --duration 30 --fps 60 --exposure-us 5000 --gain 6 --width 1440 --height 1080 --preview --preview-before-start
```

每组采集后检查：

```powershell
dir D:\CaptureData\2026-XX-XX_car_fast_lateral_001
dir D:\CaptureData\2026-XX-XX_car_fast_lateral_001\images
```

## FzMotion CSV

每组 session 的 CSV 建议保存为：

```text
D:\CaptureData\FZmotion_Data\<session_id>.csv
```

至少记录：

- session 名
- 相机刚体名
- 小车刚体名
- 采集开始和结束时间
- 是否有遮挡、灯光变化或异常

## 采集质量检查

```powershell
python .\scripts\check_capture_quality.py --capture-root D:\CaptureData\<session_id> --output-dir D:\CaptureData\results\capture_quality\<session_id> --plot
```

## 同步前扫描

```powershell
python .\scripts\sync_capture_batch_to_host.py --local-root D:\CaptureData --host-root Z:\captures --plan-only
```

## 正式同步

```powershell
python .\scripts\sync_capture_batch_to_host.py --local-root D:\CaptureData --host-root Z:\captures --verify
```

## 实验结束后

确认：

- 所有 session 都在 `D:\CaptureData`。
- 所有 CSV 都已保存。
- `Z:\captures` 中能看到同步结果。
- 重要数据主机端也能看到。
- 记录当天异常，例如掉帧、光照不足、动捕丢刚体。

